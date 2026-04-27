"""Calendly connector — event types, scheduled events, availability, booking links."""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

from .connector_base import ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult

logger = logging.getLogger("connector.calendly")
_BASE = "https://api.calendly.com"


class CalendlyConnector(ConnectorBase):
    connector_id = "calendly"
    connector_name = "Calendly"
    connector_description = "Calendly API — event types, scheduled events, availability."
    connector_status = ConnectorStatus.CONNECTED
    requires_oauth = False
    required_scopes: list[str] = []

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._token = os.environ.get("CALENDLY_API_KEY", "")
        self._user_uri: str = ""
        self._data: dict[str, Any] = {}
        self._error_count = 0

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"}

    async def connect(self) -> bool:
        if not self._token:
            self._last_error = "CALENDLY_API_KEY required"
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{_BASE}/users/me", headers=self._headers())
                r.raise_for_status()
                user = r.json().get("resource", {})
                self._user_uri = user.get("uri", "")
                self._data["user"] = user
                return True
        except Exception as exc:
            self._last_error = str(exc)
            self._error_count += 1
            return False

    async def disconnect(self) -> None:
        self._data = {}
        self._user_uri = ""

    async def sync(self) -> SyncResult:
        t0 = time.monotonic()
        try:
            meetings = await self.get_upcoming_meetings()
            self._data["meetings"] = meetings
            self._last_sync = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
            self._records_synced = len(meetings)
            return SyncResult(self.connector_id, True, len(meetings), duration_ms=(time.monotonic() - t0) * 1000)
        except Exception as exc:
            self._last_error = str(exc)
            self._error_count += 1
            return SyncResult(self.connector_id, False, errors=[str(exc)], duration_ms=(time.monotonic() - t0) * 1000)

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(self.connector_id, self.connector_status,
                               last_sync=self._last_sync, last_error=self._last_error,
                               records_synced=self._records_synced, metadata={"error_count": self._error_count})

    async def get_upcoming_meetings(self, count: int = 10) -> list[dict]:
        """Return upcoming scheduled events."""
        if not self._user_uri:
            return []
        try:
            import datetime
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{_BASE}/scheduled_events",
                                params={"user": self._user_uri, "min_start_time": now,
                                        "count": count, "sort": "start_time:asc"},
                                headers=self._headers())
                r.raise_for_status()
                events = r.json().get("collection", [])
                return [{"name": e["name"], "start": e["start_time"],
                         "end": e["end_time"], "uri": e["uri"]} for e in events]
        except Exception as exc:
            logger.error("get_upcoming_meetings: %s", exc)
            return []

    async def get_booking_link(self, event_type_slug: str | None = None) -> str:
        """Return the public booking link for a specific event type or the profile."""
        user = self._data.get("user", {})
        base_url = user.get("scheduling_url", "")
        if event_type_slug:
            return f"{base_url}/{event_type_slug}"
        return base_url

    async def cancel_event(self, event_uuid: str, reason: str = "Cancelled via SOVEREIGN") -> dict[str, Any]:
        """Cancel a scheduled event."""
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.post(f"{_BASE}/scheduled_events/{event_uuid}/cancellation",
                                 json={"reason": reason}, headers={**self._headers(),
                                                                    "Content-Type": "application/json"})
                r.raise_for_status()
                return {"cancelled": True}
        except Exception as exc:
            return {"cancelled": False, "error": str(exc)}
