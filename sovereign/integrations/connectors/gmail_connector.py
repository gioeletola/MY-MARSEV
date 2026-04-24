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
    ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult,
)

logger = logging.getLogger(__name__)

_API_BASE = "https://gmail.googleapis.com/gmail/v1"


class GmailConnector(ConnectorBase):
    connector_id = "gmail"
    connector_name = "Gmail"
    connector_description = "Reads recent emails, labels, and threads from Gmail."
    connector_status = ConnectorStatus.BETA
    requires_oauth = True
    required_scopes = ["https://www.googleapis.com/auth/gmail.readonly"]

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._access_token = self._config.get("access_token") or os.getenv("GMAIL_ACCESS_TOKEN") or ""
        self._messages: list[dict] = []
        self._max_results = self._config.get("max_results", 20)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"}

    async def connect(self) -> bool:
        if not self._access_token:
            self._logger.warning("GmailConnector: no access token configured")
            self.connector_status = ConnectorStatus.DISCONNECTED
            return False
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
        if not self._access_token:
            return SyncResult(connector_id=self.connector_id, success=False, errors=["No access token"])
        try:
            import httpx
            async with httpx.AsyncClient(timeout=20.0) as client:
                # List message IDs
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
                # Fetch metadata for each (parallel, limited)
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
