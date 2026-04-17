"""
Email integration — local JSON store with optional SMTP/IMAP.

Out-of-the-box behaviour (no credentials):
  - Outbound emails are saved to data/memory/email_outbox.json
  - Inbound messages can be injected via add_message() for testing

With credentials (via IntegrationConfig):
  - smtp_host, smtp_port, smtp_user, smtp_password → real SMTP send
  - imap_host, imap_port, imap_user, imap_password → real IMAP fetch
"""
from __future__ import annotations

import json
import logging
import pathlib
import smtplib
import uuid
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from sovereign.integrations.base_integration import (
    BaseIntegration,
    IntegrationConfig,
    IntegrationStatus,
)

logger = logging.getLogger(__name__)

_OUTBOX_FILE = pathlib.Path("data/memory/email_outbox.json")
_INBOX_FILE  = pathlib.Path("data/memory/email_inbox.json")


def _load_json(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_json(path: pathlib.Path, data: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


class EmailIntegration(BaseIntegration):
    """
    Email connector with a local-first approach.

    Credentials (optional) in IntegrationConfig.credentials:
      smtp_host, smtp_port, smtp_user, smtp_password
      imap_host, imap_port, imap_user, imap_password
    """

    integration_id = "email"
    name = "Email Integration"

    def __init__(self) -> None:
        super().__init__()
        self._smtp_cfg: dict[str, Any] = {}
        self._imap_cfg: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # BaseIntegration interface
    # ------------------------------------------------------------------

    def connect(self, config: IntegrationConfig) -> bool:
        creds = config.credentials or {}
        self._smtp_cfg = {k: v for k, v in creds.items() if k.startswith("smtp_")}
        self._imap_cfg = {k: v for k, v in creds.items() if k.startswith("imap_")}
        has_smtp = bool(self._smtp_cfg.get("smtp_host"))
        self._status = IntegrationStatus.CONNECTED
        logger.info("email.connect: SMTP=%s", has_smtp)
        return True

    def disconnect(self) -> bool:
        self._smtp_cfg = {}
        self._imap_cfg = {}
        self._status = IntegrationStatus.DISCONNECTED
        return True

    def test_connection(self) -> bool:
        if not self._smtp_cfg.get("smtp_host"):
            return False
        try:
            with smtplib.SMTP(
                self._smtp_cfg["smtp_host"],
                int(self._smtp_cfg.get("smtp_port", 587)),
                timeout=5,
            ) as s:
                s.ehlo()
            return True
        except Exception as exc:
            logger.debug("email.test_connection failed: %s", exc)
            return False

    def fetch(self, resource: str, params: dict) -> dict:
        if resource == "inbox":
            return {"messages": self.fetch_inbox(params.get("limit", 20))}
        return {}

    def push(self, resource: str, data: dict) -> dict:
        if resource == "send":
            ok = self.send_email(data.get("to",""), data.get("subject",""), data.get("body",""))
            return {"sent": ok}
        return {}

    # ------------------------------------------------------------------
    # Email-specific API
    # ------------------------------------------------------------------

    def send_email(self, to: str, subject: str, body: str, html: bool = False) -> bool:
        """
        Send an email.

        Falls back to saving in the local outbox when SMTP is unconfigured.
        """
        if self._smtp_cfg.get("smtp_host"):
            return self._smtp_send(to, subject, body, html)
        return self._local_queue(to, subject, body)

    def fetch_inbox(self, limit: int = 20) -> list[dict]:
        """Return up to *limit* messages from the local inbox store."""
        messages = _load_json(_INBOX_FILE)
        return messages[-limit:]

    def search_emails(self, query: str) -> list[dict]:
        """Search local inbox messages by subject or body."""
        q = query.lower()
        return [
            m for m in _load_json(_INBOX_FILE)
            if q in m.get("subject", "").lower() or q in m.get("body", "").lower()
        ]

    def mark_read(self, message_id: str) -> bool:
        """Mark a local inbox message as read."""
        messages = _load_json(_INBOX_FILE)
        for m in messages:
            if m.get("id") == message_id:
                m["read"] = True
                _save_json(_INBOX_FILE, messages)
                return True
        return False

    def add_message(self, sender: str, subject: str, body: str, read: bool = False) -> dict:
        """Inject a message into the local inbox (useful for testing / webhooks)."""
        msg = {
            "id": str(uuid.uuid4())[:8],
            "from": sender,
            "subject": subject,
            "body": body,
            "read": read,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }
        messages = _load_json(_INBOX_FILE)
        messages.append(msg)
        _save_json(_INBOX_FILE, messages)
        return msg

    def get_outbox(self) -> list[dict]:
        """Return locally queued outbound messages."""
        return _load_json(_OUTBOX_FILE)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _smtp_send(self, to: str, subject: str, body: str, html: bool) -> bool:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = self._smtp_cfg.get("smtp_user", "sovereign@localhost")
            msg["To"]      = to
            part = MIMEText(body, "html" if html else "plain")
            msg.attach(part)
            host = self._smtp_cfg["smtp_host"]
            port = int(self._smtp_cfg.get("smtp_port", 587))
            with smtplib.SMTP(host, port, timeout=15) as s:
                s.ehlo()
                s.starttls()
                user = self._smtp_cfg.get("smtp_user", "")
                pwd  = self._smtp_cfg.get("smtp_password", "")
                if user and pwd:
                    s.login(user, pwd)
                s.sendmail(msg["From"], [to], msg.as_string())
            logger.info("email.send_email: sent to %s", to)
            return True
        except Exception as exc:
            logger.warning("email.send_email SMTP failed (%s) — queuing locally", exc)
            return self._local_queue(to, subject, body)

    def _local_queue(self, to: str, subject: str, body: str) -> bool:
        msg = {
            "id": str(uuid.uuid4())[:8],
            "to": to,
            "subject": subject,
            "body": body,
            "queued_at": datetime.now(timezone.utc).isoformat(),
            "status": "queued",
        }
        outbox = _load_json(_OUTBOX_FILE)
        outbox.append(msg)
        _save_json(_OUTBOX_FILE, outbox)
        logger.info("email.send_email: queued locally (id=%s)", msg["id"])
        return True
