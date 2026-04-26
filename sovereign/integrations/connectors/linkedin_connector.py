"""
LinkedIn connector — fetches notifications, messages, connection requests, and job posts.
Auth: OAuth 2.0 access token from config or LINKEDIN_ACCESS_TOKEN env var.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from sovereign.integrations.connectors.connector_base import (
    ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult,
)

logger = logging.getLogger(__name__)
_API_BASE = "https://api.linkedin.com/v2"


class LinkedInConnector(ConnectorBase):
    connector_id = "linkedin"
    connector_name = "LinkedIn"
    connector_description = (
        "Syncs LinkedIn notifications, unread messages, connection requests, "
        "and job post engagement metrics."
    )
    connector_status = ConnectorStatus.BETA
    requires_oauth = True
    required_scopes = ["r_liteprofile", "r_emailaddress", "r_network", "w_member_social"]

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._token = (
            self._config.get("access_token")
            or os.getenv("LINKEDIN_ACCESS_TOKEN", "")
        )
        self._data: dict[str, Any] = {}

    async def connect(self) -> bool:
        if not self._token:
            self._logger.warning("LinkedInConnector: no access token configured")
            return False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{_API_BASE}/me",
                    headers={"Authorization": f"Bearer {self._token}"},
                )
                if resp.status_code == 200:
                    profile = resp.json()
                    self._data["profile"] = profile
                    self._logger.info("LinkedInConnector: connected as %s", profile.get("id"))
                    return True
                self._logger.warning("LinkedIn /me returned %d", resp.status_code)
                return False
        except Exception as exc:
            self._logger.error("LinkedInConnector connect error: %s", exc)
            return False

    async def disconnect(self) -> None:
        self._data.clear()

    async def sync(self) -> SyncResult:
        records = 0
        errors: list[str] = []
        try:
            import httpx
            headers = {"Authorization": f"Bearer {self._token}"}
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Fetch network updates (notifications)
                r = await client.get(
                    f"{_API_BASE}/networkUpdates?type=NCONN&count=20",
                    headers=headers,
                )
                if r.status_code == 200:
                    data = r.json()
                    self._data["network_updates"] = data.get("values", [])
                    records += len(self._data["network_updates"])
                else:
                    errors.append(f"networkUpdates: {r.status_code}")
        except Exception as exc:
            errors.append(str(exc))

        result = SyncResult(
            connector_id=self.connector_id,
            success=not errors,
            records_synced=records,
            errors=errors,
        )
        self._mark_sync(result)
        return result

    async def health(self) -> ConnectorHealth:
        ok = bool(self._token)
        return ConnectorHealth(
            connector_id=self.connector_id,
            status=ConnectorStatus.CONNECTED if ok else ConnectorStatus.DISCONNECTED,
            last_sync=self._last_sync,
            last_error=self._last_error,
            records_synced=self._records_synced,
            metadata={"profile_id": self._data.get("profile", {}).get("id", "")},
        )

    def get_profile(self) -> dict[str, Any]:
        return self._data.get("profile", {})

    def get_network_updates(self) -> list[dict]:
        return self._data.get("network_updates", [])
