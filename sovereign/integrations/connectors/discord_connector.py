"""Discord connector — guilds, channels, messages, webhooks via Bot token."""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

from .connector_base import ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult

logger = logging.getLogger("connector.discord")
_BASE = "https://discord.com/api/v10"


class DiscordConnector(ConnectorBase):
    connector_id = "discord"
    connector_name = "Discord"
    connector_description = "Discord Bot — guilds, channels, messages, webhooks."
    connector_status = ConnectorStatus.CONNECTED
    requires_oauth = False
    required_scopes: list[str] = []

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._token = os.environ.get("DISCORD_BOT_TOKEN", "")
        self._data: dict[str, Any] = {}
        self._error_count = 0

    def _headers(self) -> dict:
        return {"Authorization": f"Bot {self._token}"}

    async def connect(self) -> bool:
        if not self._token:
            self._last_error = "DISCORD_BOT_TOKEN required"
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{_BASE}/users/@me", headers=self._headers())
                r.raise_for_status()
                self._data["bot"] = r.json()
                return True
        except Exception as exc:
            self._last_error = str(exc)
            self._error_count += 1
            return False

    async def disconnect(self) -> None:
        self._data = {}

    async def sync(self) -> SyncResult:
        t0 = time.monotonic()
        try:
            guilds = await self.get_guild_stats()
            self._data["guilds"] = guilds
            self._last_sync = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
            count = len(guilds) if isinstance(guilds, list) else 1
            self._records_synced = count
            return SyncResult(self.connector_id, True, count, duration_ms=(time.monotonic() - t0) * 1000)
        except Exception as exc:
            self._last_error = str(exc)
            self._error_count += 1
            return SyncResult(self.connector_id, False, errors=[str(exc)], duration_ms=(time.monotonic() - t0) * 1000)

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(self.connector_id, self.connector_status,
                               last_sync=self._last_sync, last_error=self._last_error,
                               records_synced=self._records_synced, metadata={"error_count": self._error_count})

    async def send_message(self, channel_id: str, content: str) -> dict[str, Any]:
        """Send a message to a channel."""
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.post(f"{_BASE}/channels/{channel_id}/messages",
                                 json={"content": content}, headers=self._headers())
                r.raise_for_status()
                return {"sent": True, "message_id": r.json().get("id")}
        except Exception as exc:
            return {"sent": False, "error": str(exc)}

    async def get_guild_stats(self) -> list[dict]:
        """Return list of guilds the bot is in."""
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{_BASE}/users/@me/guilds", headers=self._headers())
                r.raise_for_status()
                return r.json()
        except Exception as exc:
            logger.error("get_guild_stats: %s", exc)
            return []

    async def create_webhook(self, channel_id: str, name: str = "SOVEREIGN") -> dict[str, Any]:
        """Create a webhook in a channel."""
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.post(f"{_BASE}/channels/{channel_id}/webhooks",
                                 json={"name": name}, headers=self._headers())
                r.raise_for_status()
                return r.json()
        except Exception as exc:
            return {"error": str(exc)}
