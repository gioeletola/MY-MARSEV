<<<<<<< HEAD
"""Notion integration — Notion API v1 connector."""
=======
"""Notion integration — pages and databases via the Notion API."""
>>>>>>> b0c71f2 (feat(multi-provider+h24): OpenAI/Gemini providers, H24 worker pool, watchdog, health alerter, live integrations)
from __future__ import annotations

import logging
import os
<<<<<<< HEAD
from typing import Any
=======
>>>>>>> b0c71f2 (feat(multi-provider+h24): OpenAI/Gemini providers, H24 worker pool, watchdog, health alerter, live integrations)

import httpx

from sovereign.integrations.base_integration import (
    BaseIntegration,
    IntegrationConfig,
    IntegrationStatus,
)

logger = logging.getLogger(__name__)

<<<<<<< HEAD
_BASE = "https://api.notion.com/v1"
=======
_API_BASE = "https://api.notion.com/v1"
>>>>>>> b0c71f2 (feat(multi-provider+h24): OpenAI/Gemini providers, H24 worker pool, watchdog, health alerter, live integrations)
_NOTION_VERSION = "2022-06-28"


class NotionIntegration(BaseIntegration):
<<<<<<< HEAD
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
=======
    """Notion API — pages and databases."""
>>>>>>> b0c71f2 (feat(multi-provider+h24): OpenAI/Gemini providers, H24 worker pool, watchdog, health alerter, live integrations)

    integration_id = "notion"
    name = "Notion Integration"

<<<<<<< HEAD
    def __init__(self) -> None:
        super().__init__()
        self._api_key: str = ""
        self._default_database_id: str = ""
        self._http: httpx.AsyncClient | None = None
=======
    def __init__(self, api_key: str = "") -> None:
        super().__init__()
        self._api_key = api_key or os.environ.get("NOTION_API_KEY", "")
>>>>>>> b0c71f2 (feat(multi-provider+h24): OpenAI/Gemini providers, H24 worker pool, watchdog, health alerter, live integrations)

    # ------------------------------------------------------------------
    # BaseIntegration interface
    # ------------------------------------------------------------------

    def connect(self, config: IntegrationConfig) -> bool:
<<<<<<< HEAD
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
=======
        key = config.credentials.get("api_key") or config.settings.get("api_key")
        if key:
            self._api_key = key
        self._status = IntegrationStatus.CONNECTED
        logger.info("NotionIntegration.connect: key_set=%s", bool(self._api_key))
>>>>>>> b0c71f2 (feat(multi-provider+h24): OpenAI/Gemini providers, H24 worker pool, watchdog, health alerter, live integrations)
        return True

    def disconnect(self) -> bool:
        self._status = IntegrationStatus.DISCONNECTED
        return True

    def test_connection(self) -> bool:
        return bool(self._api_key)

<<<<<<< HEAD
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
=======
    def fetch(self, resource: str, params: dict) -> dict:
        """
        Fetch from Notion.

        resource="page"    → GET /v1/pages/{page_id}  (params: page_id)
        resource="search"  → POST /v1/search           (params: query, filter, ...)
        """
        if not self._api_key:
            logger.warning("NotionIntegration.fetch: no API key")
            return {}

        if resource == "page":
            page_id = params.get("page_id", "")
            if not page_id:
                return {"error": "page_id required"}
            return self._get_page(page_id)

        if resource == "search":
            return self._search(params)

        logger.warning("NotionIntegration.fetch: unknown resource '%s'", resource)
        return {}

    def push(self, resource: str, data: dict) -> dict:
        """
        Push to Notion.

        resource="page" → POST /v1/pages (create a new page)
        data: standard Notion page body (parent, properties, children, ...)
        """
        if not self._api_key:
            logger.warning("NotionIntegration.push: no API key")
            return {"ok": False, "error": "no API key"}

        if resource == "page":
            return self._create_page(data)

        logger.warning("NotionIntegration.push: unknown resource '%s'", resource)
        return {"ok": False, "error": f"unknown resource: {resource}"}

    # ------------------------------------------------------------------
    # Internal helpers
>>>>>>> b0c71f2 (feat(multi-provider+h24): OpenAI/Gemini providers, H24 worker pool, watchdog, health alerter, live integrations)
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Notion-Version": _NOTION_VERSION,
            "Content-Type": "application/json",
        }

<<<<<<< HEAD
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
=======
    def _get_page(self, page_id: str) -> dict:
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(
                    f"{_API_BASE}/pages/{page_id}",
                    headers=self._headers(),
                )
            if resp.is_success:
                return resp.json()
            return {"error": resp.text, "status_code": resp.status_code}
        except Exception as exc:
            logger.error("NotionIntegration._get_page error: %s", exc)
            return {"error": str(exc)}

    def _create_page(self, data: dict) -> dict:
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(
                    f"{_API_BASE}/pages",
                    headers=self._headers(),
                    json=data,
                )
            if resp.is_success:
                body = resp.json()
                return {"ok": True, "id": body.get("id"), "data": body}
            return {"ok": False, "error": resp.text, "status_code": resp.status_code}
        except Exception as exc:
            logger.error("NotionIntegration._create_page error: %s", exc)
            return {"ok": False, "error": str(exc)}

    def _search(self, params: dict) -> dict:
        body: dict = {}
        if "query" in params:
            body["query"] = params["query"]
        if "filter" in params:
            body["filter"] = params["filter"]
        if "sort" in params:
            body["sort"] = params["sort"]
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(
                    f"{_API_BASE}/search",
                    headers=self._headers(),
                    json=body,
                )
            if resp.is_success:
                return resp.json()
            return {"error": resp.text, "status_code": resp.status_code}
        except Exception as exc:
            logger.error("NotionIntegration._search error: %s", exc)
>>>>>>> b0c71f2 (feat(multi-provider+h24): OpenAI/Gemini providers, H24 worker pool, watchdog, health alerter, live integrations)
            return {"error": str(exc)}
