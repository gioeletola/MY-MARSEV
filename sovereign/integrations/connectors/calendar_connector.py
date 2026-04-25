"""
Calendar connector — reads events from Google Calendar via REST API (OAuth 2.0).
Also supports a local ICS file fallback for offline mode.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from sovereign.integrations.connectors.connector_base import (
    ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult,
)

logger = logging.getLogger(__name__)

_GCAL_BASE = "https://www.googleapis.com/calendar/v3"


class CalendarConnector(ConnectorBase):
    connector_id = "calendar"
    connector_name = "Google Calendar"
    connector_description = "Fetches upcoming calendar events via Google Calendar API."
    connector_status = ConnectorStatus.STUB
    requires_oauth = True
    required_scopes = ["https://www.googleapis.com/auth/calendar.readonly"]

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._access_token = (
            self._config.get("access_token")
            or os.getenv("GOOGLE_CALENDAR_ACCESS_TOKEN")
            or ""
        )
        self._calendar_id = self._config.get("calendar_id", "primary")
        self._days_ahead = self._config.get("days_ahead", 7)
        self._ics_path = self._config.get("ics_path", "")
        self._events: list[dict] = []

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"}

    async def connect(self) -> bool:
        if self._ics_path and os.path.exists(self._ics_path):
            self.connector_status = ConnectorStatus.CONNECTED
            self._logger.info("CalendarConnector: using local ICS file")
            return True
        if not self._access_token:
            self._logger.warning("CalendarConnector: no access_token configured")
            return False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{_GCAL_BASE}/calendars/{self._calendar_id}",
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    cal_name = resp.json().get("summary", self._calendar_id)
                    self._logger.info("CalendarConnector: connected to '%s'", cal_name)
                    self.connector_status = ConnectorStatus.CONNECTED
                    return True
                self._logger.warning("CalendarConnector: auth failed (%d)", resp.status_code)
        except Exception as exc:
            self._logger.error("CalendarConnector: connect error: %s", exc)
        return False

    async def disconnect(self) -> None:
        self._events = []
        self.connector_status = ConnectorStatus.DISCONNECTED

    async def sync(self) -> SyncResult:
        if self._ics_path and os.path.exists(self._ics_path):
            return await self._sync_ics()
        if not self._access_token:
            return SyncResult(connector_id=self.connector_id, success=False, errors=["No access_token"])
        return await self._sync_gcal()

    async def _sync_gcal(self) -> SyncResult:
        try:
            import httpx
            self.connector_status = ConnectorStatus.SYNCING
            now = datetime.now(timezone.utc)
            time_min = now.isoformat()
            time_max = (now + timedelta(days=self._days_ahead)).isoformat()
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{_GCAL_BASE}/calendars/{self._calendar_id}/events",
                    headers=self._headers(),
                    params={
                        "timeMin": time_min,
                        "timeMax": time_max,
                        "singleEvents": "true",
                        "orderBy": "startTime",
                        "maxResults": "50",
                    },
                )
                if resp.status_code == 200:
                    self._events = resp.json().get("items", [])
                    self.connector_status = ConnectorStatus.CONNECTED
                    result = SyncResult(
                        connector_id=self.connector_id,
                        success=True,
                        records_synced=len(self._events),
                    )
                    self._mark_sync(result)
                    return result
                return SyncResult(
                    connector_id=self.connector_id, success=False,
                    errors=[f"HTTP {resp.status_code}"],
                )
        except Exception as exc:
            self.connector_status = ConnectorStatus.ERROR
            return SyncResult(connector_id=self.connector_id, success=False, errors=[str(exc)])

    async def _sync_ics(self) -> SyncResult:
        try:
            import re
            with open(self._ics_path) as f:
                content = f.read()
            events: list[dict] = []
            for block in re.split(r"BEGIN:VEVENT", content)[1:]:
                def _field(name: str) -> str:
                    m = re.search(rf"{name}[^:]*:(.*)", block)
                    return m.group(1).strip() if m else ""
                events.append({
                    "summary": _field("SUMMARY"),
                    "dtstart": _field("DTSTART"),
                    "dtend": _field("DTEND"),
                    "description": _field("DESCRIPTION"),
                    "location": _field("LOCATION"),
                    "uid": _field("UID"),
                })
            self._events = events
            self.connector_status = ConnectorStatus.CONNECTED
            result = SyncResult(
                connector_id=self.connector_id,
                success=True,
                records_synced=len(events),
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
            records_synced=len(self._events),
            metadata={
                "calendar_id": self._calendar_id,
                "days_ahead": self._days_ahead,
                "ics_fallback": bool(self._ics_path),
            },
        )

    def get_events(self) -> list[dict]:
        return self._events

    def upcoming_titles(self, n: int = 5) -> list[str]:
        return [e.get("summary", "") for e in self._events[:n] if e.get("summary")]
