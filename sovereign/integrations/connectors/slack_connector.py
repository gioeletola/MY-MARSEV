"""
Slack connector — reads messages/mentions from Slack channels via Web API.
Auth: Bot token (xoxb-...) from vault or SLACK_BOT_TOKEN env var.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from sovereign.integrations.connectors.connector_base import (
    ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult,
)

logger = logging.getLogger(__name__)

_API_BASE = "https://slack.com/api"


class SlackConnector(ConnectorBase):
    connector_id = "slack"
    connector_name = "Slack"
    connector_description = "Reads unread mentions and DMs from Slack channels."
    connector_status = ConnectorStatus.STUB
    requires_oauth = True
    required_scopes = ["channels:history", "im:history", "users:read"]

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._token = (
            self._config.get("token")
            or os.getenv("SLACK_BOT_TOKEN")
            or ""
        )
        self._messages: list[dict] = []

    async def connect(self) -> bool:
        if not self._token:
            self._logger.warning("SlackConnector: no bot token configured")
            return False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{_API_BASE}/auth.test",
                    headers={"Authorization": f"Bearer {self._token}"},
                )
                data = resp.json()
                if data.get("ok"):
                    self._logger.info("SlackConnector: authenticated as %s", data.get("user"))
                    self.connector_status = ConnectorStatus.CONNECTED
                    return True
                self._logger.warning("SlackConnector: auth failed: %s", data.get("error"))
        except Exception as exc:
            self._logger.error("SlackConnector: connect error: %s", exc)
        return False

    async def disconnect(self) -> None:
        self._messages = []
        self.connector_status = ConnectorStatus.DISCONNECTED

    async def sync(self) -> SyncResult:
        if not self._token:
            return SyncResult(connector_id=self.connector_id, success=False, errors=["No token"])
        try:
            import httpx
            self.connector_status = ConnectorStatus.SYNCING
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{_API_BASE}/conversations.list",
                    headers={"Authorization": f"Bearer {self._token}"},
                    params={"types": "public_channel,im", "limit": "100"},
                )
                data = resp.json()
                if not data.get("ok"):
                    return SyncResult(
                        connector_id=self.connector_id, success=False,
                        errors=[data.get("error", "unknown")],
                    )

                channels = data.get("channels", [])
                messages: list[dict] = []
                for channel in channels[:10]:   # cap at 10 channels
                    ch_resp = await client.get(
                        f"{_API_BASE}/conversations.history",
                        headers={"Authorization": f"Bearer {self._token}"},
                        params={"channel": channel["id"], "limit": "20"},
                    )
                    ch_data = ch_resp.json()
                    if ch_data.get("ok"):
                        for msg in ch_data.get("messages", []):
                            msg["_channel"] = channel.get("name", channel["id"])
                            messages.append(msg)

                self._messages = messages
                self.connector_status = ConnectorStatus.CONNECTED
                result = SyncResult(
                    connector_id=self.connector_id,
                    success=True,
                    records_synced=len(messages),
                )
                self._mark_sync(result)
                return result
        except Exception as exc:
            self.connector_status = ConnectorStatus.ERROR
            return SyncResult(connector_id=self.connector_id, success=False, errors=[str(exc)])

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_id=self.connector_id,
            status=self.connector_status,
            last_sync=self._last_sync,
            last_error=self._last_error,
            records_synced=len(self._messages),
            metadata={"token_configured": bool(self._token)},
        )

    def get_messages(self) -> list[dict]:
        return self._messages
