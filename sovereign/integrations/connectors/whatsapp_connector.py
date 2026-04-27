"""WhatsApp Business connector — messages, templates, media via Meta Cloud API."""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

from .connector_base import ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult

logger = logging.getLogger("connector.whatsapp")
_BASE = "https://graph.facebook.com/v18.0"


class WhatsAppConnector(ConnectorBase):
    connector_id = "whatsapp"
    connector_name = "WhatsApp Business"
    connector_description = "WhatsApp Cloud API — messages, templates, media, status."
    connector_status = ConnectorStatus.BETA
    requires_oauth = True
    required_scopes = ["whatsapp_business_messaging", "whatsapp_business_management"]

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._token = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
        self._phone_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
        self._data: dict[str, Any] = {}
        self._error_count = 0

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    async def connect(self) -> bool:
        if not self._token or not self._phone_id:
            self._last_error = "WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID required"
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{_BASE}/{self._phone_id}", headers=self._headers())
                r.raise_for_status()
                self._data["phone"] = r.json()
                return True
        except Exception as exc:
            self._last_error = str(exc)
            self._error_count += 1
            return False

    async def disconnect(self) -> None:
        self._data = {}

    async def sync(self) -> SyncResult:
        t0 = time.monotonic()
        self._last_sync = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        return SyncResult(self.connector_id, True, 0, duration_ms=(time.monotonic() - t0) * 1000)

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(self.connector_id, self.connector_status,
                               last_sync=self._last_sync, last_error=self._last_error,
                               records_synced=self._records_synced, metadata={"error_count": self._error_count})

    async def send_message(self, to: str, text: str) -> dict[str, Any]:
        """Send a text message to a WhatsApp number (+country_code format)."""
        payload = {
            "messaging_product": "whatsapp",
            "to": to.replace("+", "").replace(" ", ""),
            "type": "text",
            "text": {"body": text},
        }
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.post(f"{_BASE}/{self._phone_id}/messages",
                                 json=payload, headers=self._headers())
                r.raise_for_status()
                return {"sent": True, "message_id": r.json().get("messages", [{}])[0].get("id")}
        except Exception as exc:
            return {"sent": False, "error": str(exc)}

    async def send_template(self, to: str, template_name: str, language: str = "en_US",
                            components: list | None = None) -> dict[str, Any]:
        """Send a pre-approved template message."""
        payload = {
            "messaging_product": "whatsapp",
            "to": to.replace("+", "").replace(" ", ""),
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language},
                "components": components or [],
            },
        }
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.post(f"{_BASE}/{self._phone_id}/messages",
                                 json=payload, headers=self._headers())
                r.raise_for_status()
                return {"sent": True}
        except Exception as exc:
            return {"sent": False, "error": str(exc)}

    async def get_message_status(self, message_id: str) -> dict[str, Any]:
        """Check delivery status of a sent message."""
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{_BASE}/{message_id}", headers=self._headers())
                r.raise_for_status()
                return r.json()
        except Exception as exc:
            return {"error": str(exc)}
