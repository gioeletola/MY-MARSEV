"""
Reddit connector — fetch posts, comments, and subreddit data via public JSON API.
No auth required for read-only public data (rate limit: 60 req/min).
OAuth optional for posting.
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

_API_BASE = "https://www.reddit.com"
_OAUTH_BASE = "https://oauth.reddit.com"


class RedditConnector(ConnectorBase):
    connector_id = "reddit"
    connector_name = "Reddit"
    connector_description = "Fetch hot/top posts, comments, search, and keyword monitoring from subreddits."
    connector_status = ConnectorStatus.CONNECTED
    requires_oauth = False

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._subreddits: list[str] = self._config.get("subreddits", ["python", "programming"])
        self._post_limit: int = self._config.get("post_limit", 25)
        self._keywords: list[str] = self._config.get("keywords", [])
        self._posts: list[dict] = []
        self._headers = {
            "User-Agent": "SovereignAIOS/1.0 (by /u/sovereign_bot)",
        }
        # Optional OAuth
        self._client_id = os.getenv("REDDIT_CLIENT_ID", "")
        self._client_secret = os.getenv("REDDIT_CLIENT_SECRET", "")

    async def connect(self) -> bool:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{_API_BASE}/r/python/hot.json?limit=1",
                    headers=self._headers,
                )
                if resp.status_code == 200:
                    self.connector_status = ConnectorStatus.CONNECTED
                    return True
                return False
        except Exception as exc:
            self._logger.error("RedditConnector connect error: %s", exc)
            return False

    async def disconnect(self) -> None:
        self._posts = []
        self.connector_status = ConnectorStatus.DISCONNECTED

    async def sync(self) -> SyncResult:
        try:
            import httpx
            self.connector_status = ConnectorStatus.SYNCING
            posts: list[dict] = []

            async with httpx.AsyncClient(timeout=20.0) as client:
                for sub in self._subreddits[:10]:
                    resp = await client.get(
                        f"{_API_BASE}/r/{sub}/hot.json",
                        params={"limit": self._post_limit},
                        headers=self._headers,
                    )
                    if resp.status_code == 200:
                        data = resp.json().get("data", {}).get("children", [])
                        for item in data:
                            p = item.get("data", {})
                            posts.append({
                                "id": p.get("id"),
                                "title": p.get("title"),
                                "subreddit": p.get("subreddit"),
                                "score": p.get("score", 0),
                                "num_comments": p.get("num_comments", 0),
                                "url": p.get("url"),
                                "permalink": f"https://reddit.com{p.get('permalink', '')}",
                                "created_utc": p.get("created_utc"),
                                "author": p.get("author"),
                                "selftext": p.get("selftext", "")[:500],
                            })

                if self._keywords:
                    for kw in self._keywords[:3]:
                        resp = await client.get(
                            f"{_API_BASE}/search.json",
                            params={"q": kw, "sort": "new", "limit": 10, "type": "link"},
                            headers=self._headers,
                        )
                        if resp.status_code == 200:
                            data = resp.json().get("data", {}).get("children", [])
                            for item in data:
                                p = item.get("data", {})
                                p["_keyword_match"] = kw
                                posts.append(p)

            self._posts = posts
            self.connector_status = ConnectorStatus.CONNECTED
            return SyncResult(connector_id=self.connector_id, success=True,
                              records_synced=len(posts), data={"posts": len(posts)})
        except Exception as exc:
            self.connector_status = ConnectorStatus.ERROR
            return SyncResult(connector_id=self.connector_id, success=False,
                              records_synced=0, errors=[str(exc)])

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_id=self.connector_id,
            status=self.connector_status,
            metadata={"subreddits": len(self._subreddits), "keywords": len(self._keywords)},
        )

    def get_posts(self, limit: int = 50) -> list[dict]:
        return self._posts[:limit]

    def search_cached(self, query: str) -> list[dict]:
        q = query.lower()
        return [p for p in self._posts if q in (p.get("title", "") + p.get("selftext", "")).lower()]
