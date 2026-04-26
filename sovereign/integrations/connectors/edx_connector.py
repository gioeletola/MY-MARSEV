"""
EdX connector — syncs enrolled courses, progress, grades, and certificates.
Auth: EdX JWT access token from config or EDX_ACCESS_TOKEN env var.
API: https://courses.edx.org/api/
"""
from __future__ import annotations

import logging
import os
from typing import Any

from sovereign.integrations.connectors.connector_base import (
    ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult,
)

logger = logging.getLogger(__name__)
_API_BASE = "https://courses.edx.org/api"


class EdXConnector(ConnectorBase):
    connector_id = "edx"
    connector_name = "EdX"
    connector_description = (
        "Syncs EdX enrolled courses, completion progress, grades, "
        "certificates earned, and learning time analytics."
    )
    connector_status = ConnectorStatus.CONNECTED
    requires_oauth = True
    required_scopes = ["profile", "email", "user_id"]

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._token = self._config.get("access_token") or os.getenv("EDX_ACCESS_TOKEN", "")
        self._username = self._config.get("username") or os.getenv("EDX_USERNAME", "")
        self._data: dict[str, Any] = {}

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"JWT {self._token}"}

    async def connect(self) -> bool:
        if not self._token:
            self._logger.warning("EdXConnector: no access token configured")
            return False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{_API_BASE}/user/v1/me", headers=self._headers())
                if resp.status_code == 200:
                    user = resp.json()
                    self._data["user"] = user
                    self._username = user.get("username", self._username)
                    self._logger.info("EdXConnector: connected as %s", self._username)
                    return True
                return False
        except Exception as exc:
            self._logger.error("EdXConnector connect error: %s", exc)
            return False

    async def disconnect(self) -> None:
        self._data.clear()

    async def sync(self) -> SyncResult:
        records = 0
        errors: list[str] = []
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Enrolled courses
                r = await client.get(
                    f"{_API_BASE}/enrollment/v1/enrollment",
                    headers=self._headers(),
                    params={"username": self._username, "page_size": 50},
                )
                if r.status_code == 200:
                    enrollments = r.json().get("results", [])
                    self._data["enrollments"] = enrollments
                    records += len(enrollments)
                else:
                    errors.append(f"enrollments: {r.status_code}")

                # Course grades
                if self._username:
                    r2 = await client.get(
                        f"{_API_BASE}/grades/v1/gradebook/{self._username}/",
                        headers=self._headers(),
                    )
                    if r2.status_code == 200:
                        grades = r2.json()
                        self._data["grades"] = grades
                        records += len(grades.get("results", []))
                    else:
                        errors.append(f"grades: {r2.status_code}")

                # Certificates
                r3 = await client.get(
                    f"{_API_BASE}/certificates/v0/certificates/{self._username}/",
                    headers=self._headers(),
                )
                if r3.status_code == 200:
                    certs = r3.json()
                    self._data["certificates"] = certs.get("results", [])
                    records += len(self._data["certificates"])

        except Exception as exc:
            errors.append(str(exc))

        result = SyncResult(self.connector_id, not errors, records, errors)
        self._mark_sync(result)
        return result

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_id=self.connector_id,
            status=ConnectorStatus.CONNECTED if self._token else ConnectorStatus.DISCONNECTED,
            last_sync=self._last_sync,
            last_error=self._last_error,
            records_synced=self._records_synced,
            metadata={
                "username": self._username,
                "enrolled_courses": len(self._data.get("enrollments", [])),
                "certificates": len(self._data.get("certificates", [])),
            },
        )

    def get_enrollments(self) -> list[dict]:
        return self._data.get("enrollments", [])

    def get_certificates(self) -> list[dict]:
        return self._data.get("certificates", [])

    def completion_rate(self) -> float:
        enrollments = self._data.get("enrollments", [])
        if not enrollments:
            return 0.0
        completed = sum(1 for e in enrollments if e.get("is_active") and e.get("course_details", {}).get("course_end"))
        return completed / len(enrollments)
