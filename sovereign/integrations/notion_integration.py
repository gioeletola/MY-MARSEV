"""Notion integration — pages and databases via the Notion API."""
from __future__ import annotations

import logging
import os

import httpx

from sovereign.integrations.base_integration import (
    BaseIntegration,
    IntegrationConfig,
    IntegrationStatus,
)

logger = logging.getLogger(__name__)

_API_BASE = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"


class NotionIntegration(BaseIntegration):
    """Notion API — pages and databases."""

    integration_id = "notion"
    name = "Notion Integration"

    def __init__(self, api_key: str = "") -> None:
        super().__init__()
        self._api_key = api_key or os.environ.get("NOTION_API_KEY", "")

    # ------------------------------------------------------------------
    # BaseIntegration interface
    # ------------------------------------------------------------------

    def connect(self, config: IntegrationConfig) -> bool:
        key = config.credentials.get("api_key") or config.settings.get("api_key")
        if key:
            self._api_key = key
        self._status = IntegrationStatus.CONNECTED
        logger.info("NotionIntegration.connect: key_set=%s", bool(self._api_key))
        return True

    def disconnect(self) -> bool:
        self._status = IntegrationStatus.DISCONNECTED
        return True

    def test_connection(self) -> bool:
        return bool(self._api_key)

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
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Notion-Version": _NOTION_VERSION,
            "Content-Type": "application/json",
        }

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
            return {"error": str(exc)}
