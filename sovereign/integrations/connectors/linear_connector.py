"""
Linear connector — fetches issues/cycles assigned to the user via Linear GraphQL API.
Auth: API key from vault or LINEAR_API_KEY env var.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from sovereign.integrations.connectors.connector_base import (
    ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult,
)

logger = logging.getLogger(__name__)

_API_URL = "https://api.linear.app/graphql"

_VIEWER_ISSUES_QUERY = """
query ViewerIssues($first: Int!) {
  viewer {
    assignedIssues(first: $first, filter: { state: { type: { nin: ["completed", "cancelled"] } } }) {
      nodes {
        id
        title
        description
        priority
        state { name type }
        team { name }
        createdAt
        updatedAt
        dueDate
        url
      }
    }
  }
}
"""


class LinearConnector(ConnectorBase):
    connector_id = "linear"
    connector_name = "Linear"
    connector_description = "Fetches assigned issues and active cycles from Linear."
    connector_status = ConnectorStatus.STUB
    requires_oauth = False  # API key auth

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._api_key = (
            self._config.get("api_key")
            or os.getenv("LINEAR_API_KEY")
            or ""
        )
        self._issues: list[dict] = []

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": self._api_key,
            "Content-Type": "application/json",
        }

    async def connect(self) -> bool:
        if not self._api_key:
            self._logger.warning("LinearConnector: no API key configured")
            return False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    _API_URL,
                    headers=self._headers(),
                    json={"query": "{ viewer { id name email } }"},
                )
                data = resp.json()
                viewer = data.get("data", {}).get("viewer")
                if viewer:
                    self._logger.info("LinearConnector: authenticated as %s", viewer.get("name"))
                    self.connector_status = ConnectorStatus.CONNECTED
                    return True
                self._logger.warning("LinearConnector: auth failed: %s", data.get("errors"))
        except Exception as exc:
            self._logger.error("LinearConnector: connect error: %s", exc)
        return False

    async def disconnect(self) -> None:
        self._issues = []
        self.connector_status = ConnectorStatus.DISCONNECTED

    async def sync(self) -> SyncResult:
        if not self._api_key:
            return SyncResult(connector_id=self.connector_id, success=False, errors=["No API key"])
        try:
            import httpx
            self.connector_status = ConnectorStatus.SYNCING
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    _API_URL,
                    headers=self._headers(),
                    json={"query": _VIEWER_ISSUES_QUERY, "variables": {"first": 50}},
                )
                data = resp.json()
                issues = (
                    data.get("data", {})
                    .get("viewer", {})
                    .get("assignedIssues", {})
                    .get("nodes", [])
                )
                self._issues = issues
                self.connector_status = ConnectorStatus.CONNECTED
                result = SyncResult(
                    connector_id=self.connector_id,
                    success=True,
                    records_synced=len(issues),
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
            records_synced=len(self._issues),
            metadata={"api_key_configured": bool(self._api_key)},
        )

    def get_issues(self) -> list[dict]:
        return self._issues
