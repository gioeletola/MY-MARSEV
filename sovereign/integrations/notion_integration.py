"""Notion integration — Notion API v1 connector."""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from sovereign.integrations.base_integration import (
    BaseIntegration,
    IntegrationConfig,
    IntegrationStatus,
)

logger = logging.getLogger(__name__)

_BASE = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"


class NotionIntegration(BaseIntegration):
    """Notion API connector.

    Credentials (via ``IntegrationConfig.credentials``):
        api_key             — Notion integration token
        default_database_id — Used when parent_id is omitted on page creation

    Supported operations:

    ``fetch(resource='page', params={'page_id': '...'})``
        GET /v1/pages/{page_id}

    ``fetch(resource='search', params={'query': '...'})``
        POST /v1/search

    ``push(resource='page', data={'parent_id': '...', 'title': '...', 'content': '...'})``
        POST /v1/pages
    """

    integration_id = "notion"
    name = "Notion Integration"

    def __init__(self) -> None:
        super().__init__()
        self._api_key: str = ""
        self._default_database_id: str = ""
        self._http: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # BaseIntegration interface
    # ------------------------------------------------------------------

    def connect(self, config: IntegrationConfig) -> bool:
        creds = config.credentials
        self._api_key = (
            creds.get("api_key")
            or os.environ.get("NOTION_API_KEY", "")
        )
        self._default_database_id = (
            creds.get("default_database_id")
            or os.environ.get("NOTION_DATABASE_ID", "")
        )

        if not self._api_key:
            logger.warning("NotionIntegration: no api_key — disabled")
            self._status = IntegrationStatus.DISCONNECTED
            return False

        self._http = httpx.AsyncClient(timeout=30.0)
        self._status = IntegrationStatus.CONNECTED
        logger.info("NotionIntegration connected")
        return True

    def disconnect(self) -> bool:
        self._status = IntegrationStatus.DISCONNECTED
        return True

    def test_connection(self) -> bool:
        return bool(self._api_key)

    def fetch(self, resource: str, params: dict[str, Any]) -> dict[str, Any]:
        """Fetch a Notion resource synchronously."""
        import asyncio as _asyncio

        try:
            loop = _asyncio.new_event_loop()
            result = loop.run_until_complete(self._fetch_async(resource, params))
            loop.close()
            return result
        except Exception as exc:
            return {"error": str(exc)}

    def push(self, resource: str, data: dict[str, Any]) -> dict[str, Any]:
        """Push data to a Notion resource synchronously."""
        import asyncio as _asyncio

        try:
            loop = _asyncio.new_event_loop()
            result = loop.run_until_complete(self._push_async(resource, data))
            loop.close()
            return result
        except Exception as exc:
            return {"error": str(exc)}

    # ------------------------------------------------------------------
    # Async helpers
    # ------------------------------------------------------------------

    async def _fetch_async(
        self, resource: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        if not self._api_key:
            return {"error": "no_api_key"}

        if resource == "page":
            page_id = params.get("page_id", "")
            return await self._get(f"/pages/{page_id}")

        if resource == "search":
            query = params.get("query", "")
            return await self._post_req("/search", {"query": query})

        return {"error": f"unknown resource: {resource}"}

    async def _push_async(
        self, resource: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        if not self._api_key:
            return {"error": "no_api_key"}

        if resource == "page":
            return await self._create_page(data)

        return {"error": f"unknown resource: {resource}"}

    async def _create_page(self, data: dict[str, Any]) -> dict[str, Any]:
        parent_id = data.get("parent_id") or self._default_database_id
        title = data.get("title", "Untitled")
        content = data.get("content", "")

        payload: dict[str, Any] = {
            "parent": {"database_id": parent_id},
            "properties": {
                "Name": {
                    "title": [{"text": {"content": title}}]
                }
            },
        }
        if content:
            payload["children"] = [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": content}}]
                    },
                }
            ]

        return await self._post_req("/pages", payload)

    # ------------------------------------------------------------------
    # HTTP primitives
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Notion-Version": _NOTION_VERSION,
            "Content-Type": "application/json",
        }

    async def _get(self, path: str) -> dict[str, Any]:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=30.0)
        try:
            resp = await self._http.get(
                f"{_BASE}{path}", headers=self._headers()
            )
            return resp.json()  # type: ignore[return-value]
        except Exception as exc:
            logger.error("NotionIntegration GET %s error: %s", path, exc)
            return {"error": str(exc)}

    async def _post_req(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=30.0)
        try:
            resp = await self._http.post(
                f"{_BASE}{path}", json=payload, headers=self._headers()
            )
            return resp.json()  # type: ignore[return-value]
        except Exception as exc:
            logger.error("NotionIntegration POST %s error: %s", path, exc)
            return {"error": str(exc)}
