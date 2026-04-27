"""
Linear connector — fetches issues/cycles assigned to the user via Linear GraphQL API.
Auth: API key from vault or LINEAR_API_KEY env var.
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

_API_URL = "https://api.linear.app/graphql"

_VIEWER_ISSUES_QUERY = """
query ViewerIssues($first: Int!, $state: String) {
  viewer {
    assignedIssues(first: $first, filter: { state: { type: { nin: ["completed", "cancelled"] } } }) {
      nodes {
        id
        title
        description
        priority
        state { id name type }
        team { id name }
        createdAt
        updatedAt
        dueDate
        url
      }
    }
  }
}
"""

_TEAM_ISSUES_QUERY = """
query TeamIssues($teamId: String!, $first: Int!) {
  team(id: $teamId) {
    issues(first: $first) {
      nodes {
        id
        title
        description
        priority
        state { id name type }
        assignee { name email }
        createdAt
        updatedAt
        dueDate
        url
      }
    }
  }
}
"""

_CREATE_ISSUE_MUTATION = """
mutation CreateIssue($teamId: String!, $title: String!, $description: String, $priority: Int) {
  issueCreate(input: {
    teamId: $teamId
    title: $title
    description: $description
    priority: $priority
  }) {
    success
    issue {
      id
      title
      url
      state { name }
      priority
      createdAt
    }
  }
}
"""

_UPDATE_ISSUE_STATE_MUTATION = """
mutation UpdateIssueState($issueId: String!, $stateId: String!) {
  issueUpdate(id: $issueId, input: { stateId: $stateId }) {
    success
    issue {
      id
      title
      url
      state { id name type }
      updatedAt
    }
  }
}
"""


class LinearConnector(ConnectorBase):
    connector_id = "linear"
    connector_name = "Linear"
    connector_description = "Fetches assigned issues and active cycles from Linear."
    connector_status = ConnectorStatus.CONNECTED
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

    async def _gql(self, query: str, variables: dict | None = None) -> dict:
        """Execute a GraphQL query/mutation and return the response dict."""
        import httpx
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(_API_URL, headers=self._headers(), json=payload)
            resp.raise_for_status()
            return resp.json()

    async def connect(self) -> bool:
        if not self._api_key:
            self._logger.warning("LinearConnector: no API key configured")
            return False
        try:
            data = await self._gql("{ viewer { id name email } }")
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
            self.connector_status = ConnectorStatus.SYNCING
            issues = await self.get_assigned_issues()
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

    # ------------------------------------------------------------------
    # Domain methods
    # ------------------------------------------------------------------

    async def get_assigned_issues(self, state: str = "started") -> list[dict]:
        """Return issues assigned to the current viewer, filtered by state type."""
        data = await self._gql(
            _VIEWER_ISSUES_QUERY,
            {"first": 50, "state": state},
        )
        return (
            data.get("data", {})
            .get("viewer", {})
            .get("assignedIssues", {})
            .get("nodes", [])
        )

    async def get_team_issues(self, team_id: str, limit: int = 20) -> list[dict]:
        """Return issues for the given team."""
        data = await self._gql(_TEAM_ISSUES_QUERY, {"teamId": team_id, "first": limit})
        return (
            data.get("data", {})
            .get("team", {})
            .get("issues", {})
            .get("nodes", [])
        )

    async def create_issue(
        self,
        team_id: str,
        title: str,
        description: str = "",
        priority: int = 2,
    ) -> dict:
        """Create a new issue and return the created issue dict."""
        data = await self._gql(
            _CREATE_ISSUE_MUTATION,
            {"teamId": team_id, "title": title, "description": description, "priority": priority},
        )
        result = data.get("data", {}).get("issueCreate", {})
        if not result.get("success"):
            errors = data.get("errors", [])
            raise RuntimeError(f"LinearConnector: create_issue failed: {errors}")
        return result.get("issue", {})

    async def update_issue_state(self, issue_id: str, state_id: str) -> dict:
        """Update the workflow state of an issue."""
        data = await self._gql(
            _UPDATE_ISSUE_STATE_MUTATION,
            {"issueId": issue_id, "stateId": state_id},
        )
        result = data.get("data", {}).get("issueUpdate", {})
        if not result.get("success"):
            errors = data.get("errors", [])
            raise RuntimeError(f"LinearConnector: update_issue_state failed: {errors}")
        return result.get("issue", {})

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def get_issues(self) -> list[dict]:
        return self._issues
