"""
Slack connector — reads messages/mentions and posts to Slack channels via Web API.
Auth: Bot token (xoxb-...) from vault or SLACK_BOT_TOKEN env var.
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

_API_BASE = "https://slack.com/api"


class SlackConnector(ConnectorBase):
    connector_id = "slack"
    connector_name = "Slack"
    connector_description = "Reads unread mentions and DMs from Slack channels; supports posting messages and files."
    connector_status = ConnectorStatus.CONNECTED
    requires_oauth = True
    required_scopes = [
        "channels:history",
        "channels:read",
        "chat:write",
        "files:write",
        "im:history",
        "users:read",
    ]

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._token = (
            self._config.get("token")
            or os.getenv("SLACK_BOT_TOKEN")
            or ""
        )
        self._messages: list[dict] = []

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        if not self._token:
            self._logger.warning("SlackConnector: no bot token configured")
            return False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{_API_BASE}/auth.test",
                    headers=self._auth_headers(),
                )
                data = resp.json()
                if data.get("ok"):
                    self._logger.info(
                        "SlackConnector: authenticated as %s (team: %s)",
                        data.get("user"),
                        data.get("team"),
                    )
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
                    headers=self._auth_headers(),
                    params={"types": "public_channel,im", "limit": "100"},
                )
                data = resp.json()
                if not data.get("ok"):
                    return SyncResult(
                        connector_id=self.connector_id,
                        success=False,
                        errors=[data.get("error", "unknown")],
                    )

                channels = data.get("channels", [])
                messages: list[dict] = []
                for channel in channels[:10]:  # cap at 10 channels
                    ch_resp = await client.get(
                        f"{_API_BASE}/conversations.history",
                        headers=self._auth_headers(),
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

    # ------------------------------------------------------------------
    # Domain methods
    # ------------------------------------------------------------------

    async def send_message(
        self,
        channel: str,
        text: str,
        blocks: list[dict] | None = None,
    ) -> dict:
        """
        Post a message to a Slack channel.
        `channel` can be a channel ID, name (e.g. #general), or user ID for DMs.
        Returns the Slack message object dict.
        """
        if not self._token:
            raise RuntimeError("SlackConnector: no bot token configured")
        import httpx
        payload: dict[str, Any] = {"channel": channel, "text": text}
        if blocks:
            payload["blocks"] = blocks
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{_API_BASE}/chat.postMessage",
                headers={**self._auth_headers(), "Content-Type": "application/json; charset=utf-8"},
                json=payload,
            )
            data = resp.json()
            if data.get("ok"):
                return data.get("message", {})
            raise RuntimeError(f"SlackConnector: send_message failed: {data.get('error')}")

    async def get_channels(self, limit: int = 20) -> list[dict]:
        """
        Return a list of public channels the bot has access to.
        Each item is a Slack Channel object dict.
        """
        if not self._token:
            return []
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{_API_BASE}/conversations.list",
                headers=self._auth_headers(),
                params={"types": "public_channel", "limit": str(limit)},
            )
            data = resp.json()
            if data.get("ok"):
                return data.get("channels", [])
            self._logger.warning("SlackConnector: get_channels failed: %s", data.get("error"))
            return []

    async def get_channel_history(self, channel: str, limit: int = 10) -> list[dict]:
        """
        Return recent messages from a channel.
        `channel` is a channel ID (e.g. C1234567).
        """
        if not self._token:
            return []
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{_API_BASE}/conversations.history",
                headers=self._auth_headers(),
                params={"channel": channel, "limit": str(limit)},
            )
            data = resp.json()
            if data.get("ok"):
                return data.get("messages", [])
            self._logger.warning(
                "SlackConnector: get_channel_history failed for %s: %s",
                channel,
                data.get("error"),
            )
            return []

    async def upload_file(
        self,
        channel: str,
        content: str,
        filename: str,
        title: str = "",
    ) -> dict:
        """
        Upload a text file to a Slack channel.
        Returns the Slack File object dict.
        """
        if not self._token:
            raise RuntimeError("SlackConnector: no bot token configured")
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{_API_BASE}/files.upload",
                headers=self._auth_headers(),
                data={
                    "channels": channel,
                    "filename": filename,
                    "title": title or filename,
                    "content": content,
                },
            )
            data = resp.json()
            if data.get("ok"):
                return data.get("file", {})
            raise RuntimeError(f"SlackConnector: upload_file failed: {data.get('error')}")

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def get_messages(self) -> list[dict]:
        return self._messages
