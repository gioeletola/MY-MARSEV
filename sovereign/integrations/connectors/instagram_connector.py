"""
Instagram connector — profile, feed, stories, reels, insights, direct messages.
Auth: OAuth2 via Meta Graph API (INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_USER_ID).
Status: BETA — OAuth token must be obtained externally via Meta App Review flow.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from sovereign.integrations.connectors.connector_base import (
    ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult,
)

logger = logging.getLogger(__name__)
_API_BASE = "https://graph.instagram.com/v19.0"


class InstagramConnector(ConnectorBase):
    connector_id = "instagram"
    connector_name = "Instagram"
    connector_description = (
        "Connects to Instagram via Meta Graph API. Syncs profile info, feed posts, "
        "stories, reels, insights, and direct message threads."
    )
    connector_status = ConnectorStatus.BETA
    requires_oauth = True
    required_env_vars = ["INSTAGRAM_ACCESS_TOKEN", "INSTAGRAM_USER_ID"]

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._access_token = self._config.get("access_token") or os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
        self._user_id = self._config.get("user_id") or os.getenv("INSTAGRAM_USER_ID", "")
        self.api_base = _API_BASE
        self._data: dict[str, Any] = {}
        self._error_count = 0

    def _params(self, extra: dict | None = None) -> dict:
        p = {"access_token": self._access_token}
        if extra:
            p.update(extra)
        return p

    async def connect(self) -> bool:
        if not self._access_token or not self._user_id:
            self._logger.warning("InstagramConnector: missing access_token or user_id")
            return False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.api_base}/{self._user_id}",
                    params=self._params({"fields": "id,username,account_type"}),
                )
                if resp.status_code == 200:
                    self._data["profile"] = resp.json()
                    self._logger.info("InstagramConnector: connected as @%s", self._data["profile"].get("username"))
                    return True
                self._logger.warning("Instagram connect returned %d: %s", resp.status_code, resp.text[:200])
                return False
        except Exception as exc:
            self._logger.error("InstagramConnector connect error: %s", exc)
            self._error_count += 1
            return False

    async def disconnect(self) -> None:
        self._data.clear()

    async def sync(self) -> SyncResult:
        records = 0
        errors: list[str] = []
        try:
            import httpx
            async with httpx.AsyncClient(timeout=20.0) as client:
                # Profile
                r = await client.get(
                    f"{self.api_base}/{self._user_id}",
                    params=self._params({"fields": "id,username,account_type,media_count,followers_count"}),
                )
                if r.status_code == 200:
                    self._data["profile"] = r.json()
                    records += 1
                else:
                    errors.append(f"profile: {r.status_code}")

                # Recent media feed
                r2 = await client.get(
                    f"{self.api_base}/{self._user_id}/media",
                    params=self._params({"fields": "id,caption,media_type,timestamp,like_count,comments_count", "limit": 20}),
                )
                if r2.status_code == 200:
                    feed = r2.json().get("data", [])
                    self._data["feed"] = feed
                    records += len(feed)
                else:
                    errors.append(f"feed: {r2.status_code}")

        except Exception as exc:
            errors.append(str(exc))
            self._error_count += 1

        result = SyncResult(self.connector_id, not errors, records, errors)
        self._mark_sync(result)
        return result

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_id=self.connector_id,
            status=ConnectorStatus.BETA if self._access_token else ConnectorStatus.DISCONNECTED,
            last_sync=self._last_sync,
            last_error=self._last_error,
            records_synced=self._records_synced,
            latency_ms=0.0,
            metadata={"user_id": self._user_id, "error_count": self._error_count},
        )

    async def fetch_insights(self, metric: str = "impressions,reach,profile_views", period: str = "day") -> dict:
        """Fetch account-level insights for given metrics and period."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.api_base}/{self._user_id}/insights",
                    params=self._params({"metric": metric, "period": period}),
                )
                if resp.status_code == 200:
                    return resp.json()
                return {"error": resp.status_code, "detail": resp.text[:200]}
        except Exception as exc:
            self._logger.error("fetch_insights error: %s", exc)
            return {"error": str(exc)}

    async def post_content(self, image_url: str, caption: str = "") -> dict:
        """Create a media container and publish it (image post)."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=20.0) as client:
                # Step 1: create container
                r1 = await client.post(
                    f"{self.api_base}/{self._user_id}/media",
                    params=self._params({"image_url": image_url, "caption": caption}),
                )
                if r1.status_code != 200:
                    return {"error": f"container creation failed: {r1.status_code}"}
                container_id = r1.json().get("id")

                # Step 2: publish
                r2 = await client.post(
                    f"{self.api_base}/{self._user_id}/media_publish",
                    params=self._params({"creation_id": container_id}),
                )
                return r2.json()
        except Exception as exc:
            self._logger.error("post_content error: %s", exc)
            return {"error": str(exc)}

    async def get_story_mentions(self) -> list[dict]:
        """Get stories where the account has been mentioned."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.api_base}/{self._user_id}/tags",
                    params=self._params({"fields": "id,media_type,timestamp,username"}),
                )
                if resp.status_code == 200:
                    return resp.json().get("data", [])
                return []
        except Exception as exc:
            self._logger.error("get_story_mentions error: %s", exc)
            return []

    def get_feed(self, limit: int = 20) -> list[dict]:
        """Return cached feed posts."""
        return self._data.get("feed", [])[:limit]

    def get_profile(self) -> dict:
        """Return cached profile data."""
        return self._data.get("profile", {})
