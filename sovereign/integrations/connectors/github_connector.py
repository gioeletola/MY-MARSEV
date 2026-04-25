"""
GitHub Notifications connector — fetches unread GitHub notifications via REST API.
Auth: personal access token from secrets vault or GITHUB_TOKEN env var.
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

_API_BASE = "https://api.github.com"


class GitHubConnector(ConnectorBase):
    connector_id = "github"
    connector_name = "GitHub Notifications"
    connector_description = "Fetches unread GitHub notifications, PR reviews, and mentions."
    connector_status = ConnectorStatus.CONNECTED
    requires_oauth = False  # PAT-based

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._token = (
            self._config.get("token")
            or os.getenv("GITHUB_TOKEN")
            or os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
            or ""
        )
        self._notifications: list[dict] = []

    async def connect(self) -> bool:
        if not self._token:
            self._logger.warning("GitHubConnector: no token configured")
            return False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{_API_BASE}/user",
                    headers={"Authorization": f"token {self._token}", "Accept": "application/vnd.github.v3+json"},
                )
                if resp.status_code == 200:
                    user = resp.json().get("login", "?")
                    self._logger.info("GitHubConnector: authenticated as %s", user)
                    self.connector_status = ConnectorStatus.CONNECTED
                    return True
                self._logger.warning("GitHubConnector: auth failed (%d)", resp.status_code)
        except Exception as exc:
            self._logger.error("GitHubConnector: connect error: %s", exc)
        return False

    async def disconnect(self) -> None:
        self._notifications = []
        self.connector_status = ConnectorStatus.DISCONNECTED

    async def sync(self) -> SyncResult:
        if not self._token:
            return SyncResult(connector_id=self.connector_id, success=False, errors=["No token"])
        try:
            import httpx
            self.connector_status = ConnectorStatus.SYNCING
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{_API_BASE}/notifications",
                    headers={"Authorization": f"token {self._token}", "Accept": "application/vnd.github.v3+json"},
                    params={"all": "false", "per_page": "50"},
                )
                if resp.status_code == 200:
                    self._notifications = resp.json()
                    self.connector_status = ConnectorStatus.CONNECTED
                    return SyncResult(
                        connector_id=self.connector_id,
                        success=True,
                        records_synced=len(self._notifications),
                    )
                return SyncResult(
                    connector_id=self.connector_id, success=False,
                    errors=[f"HTTP {resp.status_code}"],
                )
        except Exception as exc:
            self.connector_status = ConnectorStatus.ERROR
            return SyncResult(connector_id=self.connector_id, success=False, errors=[str(exc)])

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_id=self.connector_id,
            status=self.connector_status,
            last_sync=self._last_sync,
            last_error=self._last_error,
            records_synced=len(self._notifications),
            metadata={"token_configured": bool(self._token)},
        )

    def get_notifications(self) -> list[dict]:
        return self._notifications
