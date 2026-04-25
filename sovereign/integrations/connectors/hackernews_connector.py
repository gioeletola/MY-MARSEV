"""
Hacker News connector — fetches top stories and job posts via official Firebase API.
No auth required.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from sovereign.integrations.connectors.connector_base import (
    ConnectorBase,
    ConnectorHealth,
    ConnectorStatus,
    SyncResult,
)

logger = logging.getLogger(__name__)

_HN_BASE = "https://hacker-news.firebaseio.com/v0"


class HackerNewsConnector(ConnectorBase):
    connector_id = "hackernews"
    connector_name = "Hacker News"
    connector_description = "Fetches top HN stories, job posts, and Ask HN threads."
    connector_status = ConnectorStatus.CONNECTED
    requires_oauth = False

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._story_count: int = self._config.get("story_count", 30)
        self._fetch_types: list[str] = self._config.get(
            "fetch_types", ["topstories", "jobstories"]
        )
        self._stories: list[dict] = []

    async def connect(self) -> bool:
        self.connector_status = ConnectorStatus.CONNECTED
        return True

    async def disconnect(self) -> None:
        self._stories = []
        self.connector_status = ConnectorStatus.DISCONNECTED

    async def sync(self) -> SyncResult:
        try:
            import httpx
            self.connector_status = ConnectorStatus.SYNCING
            stories: list[dict] = []

            async with httpx.AsyncClient(timeout=20.0) as client:
                ids: list[int] = []
                for story_type in self._fetch_types:
                    resp = await client.get(f"{_HN_BASE}/{story_type}.json")
                    if resp.status_code == 200:
                        type_ids = resp.json() or []
                        ids.extend(type_ids[: self._story_count])

                # Fetch item details concurrently (cap at 50 concurrent)
                sem = asyncio.Semaphore(10)

                async def fetch_item(item_id: int) -> dict | None:
                    async with sem:
                        try:
                            r = await client.get(f"{_HN_BASE}/item/{item_id}.json", timeout=5.0)
                            if r.status_code == 200:
                                return r.json()
                        except Exception:
                            pass
                        return None

                results = await asyncio.gather(*[fetch_item(i) for i in ids[:50]])
                stories = [r for r in results if r is not None]

            self._stories = stories
            self.connector_status = ConnectorStatus.CONNECTED
            result = SyncResult(
                connector_id=self.connector_id,
                success=True,
                records_synced=len(stories),
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
            records_synced=len(self._stories),
            metadata={"story_count": self._story_count, "types": self._fetch_types},
        )

    def get_stories(self) -> list[dict]:
        return self._stories

    def top_titles(self, n: int = 10) -> list[str]:
        return [s.get("title", "") for s in self._stories[:n] if s.get("title")]
