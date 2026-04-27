"""
Facebook connector — pages, posts, ads, events, and analytics via Meta Graph API.
Auth: OAuth2 (FACEBOOK_ACCESS_TOKEN, FACEBOOK_PAGE_ID).
Status: BETA — requires Meta App Review for advanced permissions.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from sovereign.integrations.connectors.connector_base import (
    ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult,
)

logger = logging.getLogger(__name__)
_API_BASE = "https://graph.facebook.com/v19.0"


class FacebookConnector(ConnectorBase):
    connector_id = "facebook"
    connector_name = "Facebook"
    connector_description = (
        "Connects to Facebook via Meta Graph API. Syncs pages, posts, ads performance, "
        "events, and audience analytics."
    )
    connector_status = ConnectorStatus.BETA
    requires_oauth = True
    required_env_vars = ["FACEBOOK_ACCESS_TOKEN", "FACEBOOK_PAGE_ID"]

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._access_token = self._config.get("access_token") or os.getenv("FACEBOOK_ACCESS_TOKEN", "")
        self._page_id = self._config.get("page_id") or os.getenv("FACEBOOK_PAGE_ID", "")
        self._ad_account_id = self._config.get("ad_account_id") or os.getenv("FACEBOOK_AD_ACCOUNT_ID", "")
        self.api_base = _API_BASE
        self._data: dict[str, Any] = {}
        self._error_count = 0

    def _params(self, extra: dict | None = None) -> dict:
        p = {"access_token": self._access_token}
        if extra:
            p.update(extra)
        return p

    async def connect(self) -> bool:
        if not self._access_token or not self._page_id:
            self._logger.warning("FacebookConnector: missing access_token or page_id")
            return False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.api_base}/{self._page_id}",
                    params=self._params({"fields": "id,name,fan_count,category"}),
                )
                if resp.status_code == 200:
                    self._data["page"] = resp.json()
                    self._logger.info("FacebookConnector: connected to page '%s'", self._data["page"].get("name"))
                    return True
                self._logger.warning("Facebook connect returned %d", resp.status_code)
                return False
        except Exception as exc:
            self._logger.error("FacebookConnector connect error: %s", exc)
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
                # Page info
                r = await client.get(
                    f"{self.api_base}/{self._page_id}",
                    params=self._params({"fields": "id,name,fan_count,category,about,website"}),
                )
                if r.status_code == 200:
                    self._data["page"] = r.json()
                    records += 1
                else:
                    errors.append(f"page: {r.status_code}")

                # Recent posts
                r2 = await client.get(
                    f"{self.api_base}/{self._page_id}/posts",
                    params=self._params({"fields": "id,message,created_time,likes.summary(true),comments.summary(true)", "limit": 20}),
                )
                if r2.status_code == 200:
                    posts = r2.json().get("data", [])
                    self._data["posts"] = posts
                    records += len(posts)
                else:
                    errors.append(f"posts: {r2.status_code}")

                # Events
                r3 = await client.get(
                    f"{self.api_base}/{self._page_id}/events",
                    params=self._params({"fields": "id,name,start_time,attending_count", "limit": 10}),
                )
                if r3.status_code == 200:
                    events = r3.json().get("data", [])
                    self._data["events"] = events
                    records += len(events)
                else:
                    errors.append(f"events: {r3.status_code}")

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
            metadata={"page_id": self._page_id, "error_count": self._error_count},
        )

    async def fetch_page_insights(self, metric: str = "page_impressions,page_engaged_users", period: str = "day") -> dict:
        """Fetch page-level insights for given metrics."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.api_base}/{self._page_id}/insights",
                    params=self._params({"metric": metric, "period": period}),
                )
                if resp.status_code == 200:
                    return resp.json()
                return {"error": resp.status_code, "detail": resp.text[:200]}
        except Exception as exc:
            self._logger.error("fetch_page_insights error: %s", exc)
            return {"error": str(exc)}

    async def get_ad_performance(self, date_preset: str = "last_7d") -> dict:
        """Fetch ad account performance summary."""
        if not self._ad_account_id:
            return {"error": "FACEBOOK_AD_ACCOUNT_ID not configured"}
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.api_base}/act_{self._ad_account_id}/insights",
                    params=self._params({
                        "fields": "spend,impressions,clicks,ctr,cpc,reach",
                        "date_preset": date_preset,
                    }),
                )
                if resp.status_code == 200:
                    return resp.json()
                return {"error": resp.status_code}
        except Exception as exc:
            self._logger.error("get_ad_performance error: %s", exc)
            return {"error": str(exc)}

    async def schedule_post(self, message: str, scheduled_publish_time: int) -> dict:
        """Schedule a post on the page. scheduled_publish_time is a Unix timestamp."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.api_base}/{self._page_id}/feed",
                    params=self._params({
                        "message": message,
                        "published": "false",
                        "scheduled_publish_time": scheduled_publish_time,
                    }),
                )
                return resp.json()
        except Exception as exc:
            self._logger.error("schedule_post error: %s", exc)
            return {"error": str(exc)}

    def get_page_info(self) -> dict:
        """Return cached page information."""
        return self._data.get("page", {})

    def get_recent_posts(self, limit: int = 10) -> list[dict]:
        """Return cached recent posts."""
        return self._data.get("posts", [])[:limit]
