"""
Product Hunt connector — fetch today's launches, trending products, and comment sentiment.
Uses the official PH GraphQL API (token optional for higher rate limits).
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

_GQL_BASE = "https://api.producthunt.com/v2/api/graphql"

_POSTS_QUERY = """
query TodayPosts($first: Int!) {
  posts(first: $first, order: VOTES) {
    edges {
      node {
        id
        name
        tagline
        description
        votesCount
        commentsCount
        website
        url
        topics { edges { node { name } } }
        thumbnail { url }
        createdAt
      }
    }
  }
}
"""


class ProductHuntConnector(ConnectorBase):
    connector_id = "producthunt"
    connector_name = "Product Hunt"
    connector_description = "Fetch today's top launches, trending products, and competitor monitoring from Product Hunt."
    connector_status = ConnectorStatus.CONNECTED
    requires_oauth = False

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._token = (
            self._config.get("token")
            or os.getenv("PRODUCTHUNT_TOKEN")
            or ""
        )
        self._post_limit: int = self._config.get("post_limit", 20)
        self._posts: list[dict] = []

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    async def connect(self) -> bool:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    _GQL_BASE,
                    json={"query": _POSTS_QUERY, "variables": {"first": 1}},
                    headers=self._headers(),
                )
                if resp.status_code == 200 and "errors" not in resp.json():
                    self.connector_status = ConnectorStatus.CONNECTED
                    return True
                self._logger.warning("ProductHuntConnector: API check failed %s", resp.status_code)
                return False
        except Exception as exc:
            self._logger.error("ProductHuntConnector connect error: %s", exc)
            return False

    async def disconnect(self) -> None:
        self._posts = []
        self.connector_status = ConnectorStatus.DISCONNECTED

    async def sync(self) -> SyncResult:
        try:
            import httpx
            self.connector_status = ConnectorStatus.SYNCING
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    _GQL_BASE,
                    json={"query": _POSTS_QUERY, "variables": {"first": self._post_limit}},
                    headers=self._headers(),
                )
                if resp.status_code != 200:
                    raise ValueError(f"HTTP {resp.status_code}")
                data = resp.json()
                if "errors" in data:
                    raise ValueError(str(data["errors"]))

                edges = data.get("data", {}).get("posts", {}).get("edges", [])
                self._posts = [
                    {
                        "id": e["node"]["id"],
                        "name": e["node"]["name"],
                        "tagline": e["node"]["tagline"],
                        "description": (e["node"].get("description") or "")[:400],
                        "votes": e["node"].get("votesCount", 0),
                        "comments": e["node"].get("commentsCount", 0),
                        "website": e["node"].get("website"),
                        "url": e["node"].get("url"),
                        "topics": [
                            t["node"]["name"]
                            for t in (e["node"].get("topics", {}).get("edges") or [])
                        ],
                        "thumbnail": (e["node"].get("thumbnail") or {}).get("url"),
                        "created_at": e["node"].get("createdAt"),
                    }
                    for e in edges
                ]

            self.connector_status = ConnectorStatus.CONNECTED
            return SyncResult(connector_id=self.connector_id, success=True,
                              records_synced=len(self._posts))
        except Exception as exc:
            self.connector_status = ConnectorStatus.ERROR
            return SyncResult(connector_id=self.connector_id, success=False,
                              records_synced=0, errors=[str(exc)])

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_id=self.connector_id,
            status=self.connector_status,
            metadata={"token_set": bool(self._token), "posts_cached": len(self._posts)},
        )

    def get_posts(self, limit: int = 20) -> list[dict]:
        return self._posts[:limit]

    def top_by_votes(self, n: int = 5) -> list[dict]:
        return sorted(self._posts, key=lambda p: p.get("votes", 0), reverse=True)[:n]
