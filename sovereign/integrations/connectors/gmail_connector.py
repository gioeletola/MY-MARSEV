"""
Gmail connector — reads recent emails via Gmail API (OAuth2).
Auth: OAuth2 via OAuthManager (GOOGLE_CLIENT_ID/SECRET).
Status: BETA
"""
from __future__ import annotations

import logging
import os
from typing import Any

from sovereign.integrations.connectors.connector_base import (
    ConnectorBase,
    ConnectorHealth,
    ConnectorStatus,
    SyncResult,
)

logger = logging.getLogger(__name__)

_API_BASE = "https://gmail.googleapis.com/gmail/v1"


class GmailConnector(ConnectorBase):
    connector_id = "gmail"
    connector_name = "Gmail"
    connector_description = "Reads recent emails, labels, and threads from Gmail."
    connector_status = ConnectorStatus.BETA
    requires_oauth = True
    required_scopes = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
    ]

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._access_token = self._config.get("access_token") or os.getenv("GMAIL_ACCESS_TOKEN") or ""
        self._refresh_token = self._config.get("refresh_token") or os.getenv("GMAIL_REFRESH_TOKEN") or ""
        self._messages: list[dict] = []
        self._max_results = self._config.get("max_results", 20)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"}

    async def _ensure_token(self) -> None:
        """Proactively refresh the access token if a refresh token is configured."""
        if not self._refresh_token:
            return
        try:
            from sovereign.integrations.connectors.oauth_refresh import ensure_fresh_token
            fresh = await ensure_fresh_token(self._access_token, self._refresh_token)
            if fresh and fresh != self._access_token:
                self._access_token = fresh
        except Exception as exc:
            logger.debug("GmailConnector._ensure_token: %s", exc)

    async def connect(self) -> bool:
        if not self._access_token and not self._refresh_token:
            self._logger.warning("GmailConnector: no access token configured")
            self.connector_status = ConnectorStatus.DISCONNECTED
            return False
        await self._ensure_token()
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{_API_BASE}/users/me/profile", headers=self._headers()
                )
                if resp.status_code == 200:
                    email = resp.json().get("emailAddress", "?")
                    self._logger.info("GmailConnector: connected as %s", email)
                    self.connector_status = ConnectorStatus.CONNECTED
                    return True
        except Exception as exc:
            self._logger.error("GmailConnector: connect error: %s", exc)
        return False

    async def disconnect(self) -> None:
        self._messages = []
        self.connector_status = ConnectorStatus.DISCONNECTED

    async def sync(self) -> SyncResult:
        if not self._access_token and not self._refresh_token:
            return SyncResult(connector_id=self.connector_id, success=False, errors=["No access token"])
        await self._ensure_token()
        try:
            import httpx
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(
                    f"{_API_BASE}/users/me/messages",
                    headers=self._headers(),
                    params={"maxResults": str(self._max_results), "labelIds": "INBOX"},
                )
                if resp.status_code != 200:
                    return SyncResult(
                        connector_id=self.connector_id, success=False,
                        errors=[f"HTTP {resp.status_code}"],
                    )
                msg_ids = [m["id"] for m in resp.json().get("messages", [])]
                snippets = []
                for mid in msg_ids[:10]:
                    r = await client.get(
                        f"{_API_BASE}/users/me/messages/{mid}",
                        headers=self._headers(),
                        params={"format": "metadata", "metadataHeaders": "Subject,From,Date"},
                    )
                    if r.status_code == 200:
                        snippets.append(r.json())
                self._messages = snippets
                return SyncResult(
                    connector_id=self.connector_id, success=True,
                    records_synced=len(self._messages),
                )
        except Exception as exc:
            return SyncResult(connector_id=self.connector_id, success=False, errors=[str(exc)])

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_id=self.connector_id,
            status=self.connector_status,
            last_sync=self._last_sync,
            last_error=self._last_error,
            records_synced=len(self._messages),
        )

    def get_messages(self) -> list[dict]:
        return self._messages

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    async def send_email(
        self,
        to: str | list[str],
        subject: str,
        body: str,
        html: bool = False,
        cc: str | list[str] | None = None,
        reply_to_message_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Send an email via Gmail API.
        Requires scope: https://www.googleapis.com/auth/gmail.send
        Returns {"message_id": str, "thread_id": str} on success, {"error": str} on failure.
        """
        import base64
        import email.mime.multipart
        import email.mime.text

        await self._ensure_token()
        if not self._access_token:
            return {"error": "No access token configured"}

        if html:
            msg: email.mime.multipart.MIMEMultipart | email.mime.text.MIMEText = (
                email.mime.multipart.MIMEMultipart("alternative")
            )
            msg.attach(email.mime.text.MIMEText(body, "html"))
        else:
            msg = email.mime.text.MIMEText(body, "plain")

        to_list = [to] if isinstance(to, str) else to
        msg["To"] = ", ".join(to_list)
        msg["Subject"] = subject
        if cc:
            cc_list = [cc] if isinstance(cc, str) else cc
            msg["Cc"] = ", ".join(cc_list)
        if reply_to_message_id:
            msg["In-Reply-To"] = reply_to_message_id
            msg["References"] = reply_to_message_id

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{_API_BASE}/users/me/messages/send",
                    headers={**self._headers(), "Content-Type": "application/json"},
                    json={"raw": raw},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {"message_id": data.get("id", ""), "thread_id": data.get("threadId", "")}
                return {"error": f"Gmail API error {resp.status_code}: {resp.text[:200]}"}
        except Exception as exc:
            return {"error": str(exc)}

    async def create_draft(
        self,
        to: str,
        subject: str,
        body: str,
    ) -> dict[str, Any]:
        """Create a draft email (does not send). Returns {"draft_id": str} on success."""
        import base64
        import email.mime.text

        await self._ensure_token()
        if not self._access_token:
            return {"error": "No access token configured"}

        msg = email.mime.text.MIMEText(body, "plain")
        msg["To"] = to
        msg["Subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{_API_BASE}/users/me/drafts",
                    headers={**self._headers(), "Content-Type": "application/json"},
                    json={"message": {"raw": raw}},
                )
                if resp.status_code in (200, 201):
                    return {"draft_id": resp.json().get("id", "")}
                return {"error": f"Draft API error {resp.status_code}"}
        except Exception as exc:
            return {"error": str(exc)}

    async def trash_message(self, message_id: str) -> dict[str, Any]:
        """Move a message to trash. Returns {"trashed": True} on success."""
        await self._ensure_token()
        if not self._access_token:
            return {"error": "No access token configured"}
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{_API_BASE}/users/me/messages/{message_id}/trash",
                    headers=self._headers(),
                )
                return {"trashed": resp.status_code == 200, "status": resp.status_code}
        except Exception as exc:
            return {"error": str(exc)}
