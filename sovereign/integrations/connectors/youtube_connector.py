"""
YouTube Data API v3 connector — fetch channel stats, video analytics, comments.
Auth: API key (no OAuth for public data) or OAuth for channel management.
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

_API_BASE = "https://www.googleapis.com/youtube/v3"


class YouTubeConnector(ConnectorBase):
    connector_id = "youtube"
    connector_name = "YouTube"
    connector_description = "Fetch channel statistics, recent uploads, video analytics, and trending topics via YouTube Data API v3."
    connector_status = ConnectorStatus.CONNECTED
    requires_oauth = False

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._api_key = (
            self._config.get("api_key")
            or os.getenv("YOUTUBE_API_KEY")
            or ""
        )
        self._channel_ids: list[str] = self._config.get("channel_ids", [])
        self._videos: list[dict] = []
        self._channel_stats: dict[str, Any] = {}

    async def connect(self) -> bool:
        if not self._api_key:
            self._logger.warning("YouTubeConnector: no API key configured")
            return False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{_API_BASE}/videos",
                    params={"part": "id", "chart": "mostPopular", "maxResults": 1, "key": self._api_key},
                )
                if resp.status_code == 200:
                    self.connector_status = ConnectorStatus.CONNECTED
                    return True
                self._logger.warning("YouTubeConnector: auth check failed %s", resp.status_code)
                return False
        except Exception as exc:
            self._logger.error("YouTubeConnector connect error: %s", exc)
            return False

    async def disconnect(self) -> None:
        self._videos = []
        self._channel_stats = {}
        self.connector_status = ConnectorStatus.DISCONNECTED

    async def sync(self) -> SyncResult:
        if not self._api_key:
            return SyncResult(connector_id=self.connector_id, success=False,
                              records_synced=0, errors=["No API key configured"])
        try:
            import httpx
            self.connector_status = ConnectorStatus.SYNCING
            synced = 0

            async with httpx.AsyncClient(timeout=20.0) as client:
                for channel_id in self._channel_ids[:5]:
                    stats_resp = await client.get(
                        f"{_API_BASE}/channels",
                        params={"part": "statistics,snippet", "id": channel_id, "key": self._api_key},
                    )
                    if stats_resp.status_code == 200:
                        items = stats_resp.json().get("items", [])
                        if items:
                            self._channel_stats[channel_id] = items[0]
                            synced += 1

                    videos_resp = await client.get(
                        f"{_API_BASE}/search",
                        params={
                            "part": "snippet",
                            "channelId": channel_id,
                            "maxResults": 10,
                            "order": "date",
                            "type": "video",
                            "key": self._api_key,
                        },
                    )
                    if videos_resp.status_code == 200:
                        self._videos.extend(videos_resp.json().get("items", []))
                        synced += len(videos_resp.json().get("items", []))

            self.connector_status = ConnectorStatus.CONNECTED
            return SyncResult(connector_id=self.connector_id, success=True,
                              records_synced=synced, data={"videos": len(self._videos)})
        except Exception as exc:
            self.connector_status = ConnectorStatus.ERROR
            return SyncResult(connector_id=self.connector_id, success=False,
                              records_synced=0, errors=[str(exc)])

    async def health(self) -> ConnectorHealth:
        ok = bool(self._api_key)
        return ConnectorHealth(
            connector_id=self.connector_id,
            status=ConnectorStatus.CONNECTED if ok else ConnectorStatus.ERROR,
            metadata={"api_key_set": ok, "channels_tracked": len(self._channel_ids)},
        )

    def get_videos(self) -> list[dict]:
        return list(self._videos)

    def get_channel_stats(self) -> dict[str, Any]:
        return dict(self._channel_stats)
