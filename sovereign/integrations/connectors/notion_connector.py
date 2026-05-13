"""
Notion connector — reads/writes pages, databases via Notion API v1.
Auth: NOTION_TOKEN env var or secrets vault.
Status: BETA
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

_API_BASE = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"


class NotionConnector(ConnectorBase):
    connector_id = "notion"
    connector_name = "Notion"
    connector_description = "Read and write Notion pages and databases."
    connector_status = ConnectorStatus.BETA
    requires_oauth = True
    required_scopes = ["read_content", "update_content", "insert_content"]

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._token = self._config.get("token") or os.getenv("NOTION_TOKEN") or ""
        self._pages: list[dict] = []

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Notion-Version": _NOTION_VERSION,
            "Content-Type": "application/json",
        }

    async def connect(self) -> bool:
        if not self._token:
            self._logger.warning("NotionConnector: NOTION_TOKEN not configured")
            return False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{_API_BASE}/users/me", headers=self._headers())
                if resp.status_code == 200:
                    self.connector_status = ConnectorStatus.CONNECTED
                    return True
                self._logger.warning("NotionConnector: auth failed (%d)", resp.status_code)
        except Exception as exc:
            self._logger.error("NotionConnector: connect error: %s", exc)
        return False

    async def disconnect(self) -> None:
        self._pages = []
        self.connector_status = ConnectorStatus.DISCONNECTED

    async def sync(self) -> SyncResult:
        if not self._token:
            return SyncResult(connector_id=self.connector_id, success=False, errors=["No token"])
        try:
            import httpx
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    f"{_API_BASE}/search",
                    headers=self._headers(),
                    json={"filter": {"value": "page", "property": "object"}, "page_size": 50},
                )
                if resp.status_code == 200:
                    results = resp.json().get("results", [])
                    self._pages = results
                    return SyncResult(
                        connector_id=self.connector_id, success=True,
                        records_synced=len(results),
                    )
                return SyncResult(
                    connector_id=self.connector_id, success=False,
                    errors=[f"HTTP {resp.status_code}: {resp.text[:200]}"],
                )
        except Exception as exc:
            return SyncResult(connector_id=self.connector_id, success=False, errors=[str(exc)])

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_id=self.connector_id,
            status=self.connector_status,
            last_sync=self._last_sync,
            last_error=self._last_error,
            records_synced=len(self._pages),
            metadata={"token_configured": bool(self._token)},
        )

    async def create_page(
        self,
        parent_database_id: str,
        properties: dict[str, Any],
        content_blocks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Create a new page in a Notion database.
        properties: Notion property values (see Notion API docs).
        Returns {"page_id": str, "url": str} on success, {"error": str} on failure.
        """
        if not self._token:
            return {"error": "No API token configured"}
        body: dict[str, Any] = {
            "parent": {"database_id": parent_database_id},
            "properties": properties,
        }
        if content_blocks:
            body["children"] = content_blocks
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{_API_BASE}/pages",
                    headers=self._headers(),
                    json=body,
                )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    return {"page_id": data.get("id", ""), "url": data.get("url", "")}
                return {"error": f"Notion API {resp.status_code}: {resp.text[:200]}"}
        except Exception as exc:
            return {"error": str(exc)}

    async def update_page(
        self,
        page_id: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        """Update properties of an existing Notion page."""
        if not self._token:
            return {"error": "No API token configured"}
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.patch(
                    f"{_API_BASE}/pages/{page_id}",
                    headers=self._headers(),
                    json={"properties": properties},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {"page_id": data.get("id", ""), "url": data.get("url", "")}
                return {"error": f"Notion API {resp.status_code}: {resp.text[:200]}"}
        except Exception as exc:
            return {"error": str(exc)}

    async def append_blocks(
        self,
        block_id: str,
        children: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Append content blocks to a page or block."""
        if not self._token:
            return {"error": "No API token configured"}
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.patch(
                    f"{_API_BASE}/blocks/{block_id}/children",
                    headers=self._headers(),
                    json={"children": children},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {"results": data.get("results", []), "block_id": block_id}
                return {"error": f"Notion API {resp.status_code}: {resp.text[:200]}"}
        except Exception as exc:
            return {"error": str(exc)}

    async def create_database(
        self,
        parent_page_id: str,
        title: str,
        properties_schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a new Notion database under a parent page."""
        if not self._token:
            return {"error": "No API token configured"}
        body: dict[str, Any] = {
            "parent": {"page_id": parent_page_id},
            "title": [{"type": "text", "text": {"content": title}}],
            "properties": properties_schema,
        }
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{_API_BASE}/databases",
                    headers=self._headers(),
                    json=body,
                )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    return {"database_id": data.get("id", ""), "url": data.get("url", "")}
                return {"error": f"Notion API {resp.status_code}: {resp.text[:200]}"}
        except Exception as exc:
            return {"error": str(exc)}
