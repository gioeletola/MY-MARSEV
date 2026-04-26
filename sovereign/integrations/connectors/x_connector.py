"""
X (Twitter) connector — syncs mentions, DMs, bookmarks, and trending topics.
Auth: Bearer token from config or X_BEARER_TOKEN env var.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from sovereign.integrations.connectors.connector_base import (
    ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult,
)

logger = logging.getLogger(__name__)
_API_BASE = "https://api.twitter.com/2"


class XConnector(ConnectorBase):
    connector_id = "x"
    connector_name = "X (Twitter)"
    connector_description = (
        "Syncs X mentions, DMs, bookmarks, follower analytics, "
        "and trending topics relevant to configured interests."
    )
    connector_status = ConnectorStatus.CONNECTED
    requires_oauth = True
    required_scopes = ["tweet.read", "users.read", "dm.read", "bookmark.read", "offline.access"]

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._bearer = (
            self._config.get("bearer_token")
            or os.getenv("X_BEARER_TOKEN", "")
        )
        self._user_id: str = self._config.get("user_id", "")
        self._data: dict[str, Any] = {}

    async def connect(self) -> bool:
        if not self._bearer:
            self._logger.warning("XConnector: no bearer token configured")
            return False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{_API_BASE}/users/me",
                    headers={"Authorization": f"Bearer {self._bearer}"},
                )
                if resp.status_code == 200:
                    user = resp.json().get("data", {})
                    self._user_id = user.get("id", self._user_id)
                    self._data["user"] = user
                    self._logger.info("XConnector: connected as @%s", user.get("username"))
                    return True
                return False
        except Exception as exc:
            self._logger.error("XConnector connect error: %s", exc)
            return False

    async def disconnect(self) -> None:
        self._data.clear()

    async def sync(self) -> SyncResult:
        records = 0
        errors: list[str] = []
        if not self._bearer:
            return SyncResult(self.connector_id, False, errors=["No bearer token"])

        try:
            import httpx
            headers = {"Authorization": f"Bearer {self._bearer}"}
            async with httpx.AsyncClient(timeout=15.0) as client:
                if self._user_id:
                    # Mentions timeline
                    r = await client.get(
                        f"{_API_BASE}/users/{self._user_id}/mentions",
                        headers=headers,
                        params={"max_results": 20, "tweet.fields": "created_at,public_metrics"},
                    )
                    if r.status_code == 200:
                        mentions = r.json().get("data", [])
                        self._data["mentions"] = mentions
                        records += len(mentions)
                    else:
                        errors.append(f"mentions: {r.status_code}")

                    # Bookmarks
                    r2 = await client.get(
                        f"{_API_BASE}/users/{self._user_id}/bookmarks",
                        headers=headers,
                        params={"max_results": 20},
                    )
                    if r2.status_code == 200:
                        bookmarks = r2.json().get("data", [])
                        self._data["bookmarks"] = bookmarks
                        records += len(bookmarks)
        except Exception as exc:
            errors.append(str(exc))

        result = SyncResult(self.connector_id, not errors, records, errors)
        self._mark_sync(result)
        return result

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_id=self.connector_id,
            status=ConnectorStatus.CONNECTED if self._bearer else ConnectorStatus.DISCONNECTED,
            last_sync=self._last_sync,
            last_error=self._last_error,
            records_synced=self._records_synced,
            metadata={"user_id": self._user_id, "username": self._data.get("user", {}).get("username", "")},
        )

    def get_mentions(self) -> list[dict]:
        return self._data.get("mentions", [])

    def get_bookmarks(self) -> list[dict]:
        return self._data.get("bookmarks", [])
