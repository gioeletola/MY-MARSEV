"""Strava connector — activities, stats, goals, fitness trends."""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

from .connector_base import ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult

logger = logging.getLogger("connector.strava")
_BASE = "https://www.strava.com/api/v3"


class StravaConnector(ConnectorBase):
    connector_id = "strava"
    connector_name = "Strava"
    connector_description = "Strava API — activities, weekly stats, goals, fitness trends."
    connector_status = ConnectorStatus.CONNECTED
    requires_oauth = True
    required_scopes = ["activity:read_all", "profile:read_all"]

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._token = os.environ.get("STRAVA_ACCESS_TOKEN", "")
        self._client_id = os.environ.get("STRAVA_CLIENT_ID", "")
        self._client_secret = os.environ.get("STRAVA_CLIENT_SECRET", "")
        self._refresh_token = os.environ.get("STRAVA_REFRESH_TOKEN", "")
        self._data: dict[str, Any] = {}
        self._error_count = 0

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"}

    async def _refresh(self) -> bool:
        if not all([self._client_id, self._client_secret, self._refresh_token]):
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.post("https://www.strava.com/oauth/token",
                                 data={"client_id": self._client_id, "client_secret": self._client_secret,
                                       "refresh_token": self._refresh_token, "grant_type": "refresh_token"})
                r.raise_for_status()
                self._token = r.json()["access_token"]
                return True
        except Exception:
            return False

    async def connect(self) -> bool:
        if not self._token:
            if not await self._refresh():
                self._last_error = "STRAVA_ACCESS_TOKEN or STRAVA_REFRESH_TOKEN+CLIENT_ID+SECRET required"
                return False
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{_BASE}/athlete", headers=self._headers())
                r.raise_for_status()
                self._data["athlete"] = r.json()
                return True
        except Exception as exc:
            self._last_error = str(exc)
            self._error_count += 1
            return False

    async def disconnect(self) -> None:
        self._data = {}

    async def sync(self) -> SyncResult:
        t0 = time.monotonic()
        try:
            activities = await self.get_recent_activities()
            self._data["activities"] = activities
            self._last_sync = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
            self._records_synced = len(activities)
            return SyncResult(self.connector_id, True, len(activities), duration_ms=(time.monotonic() - t0) * 1000)
        except Exception as exc:
            self._last_error = str(exc)
            self._error_count += 1
            return SyncResult(self.connector_id, False, errors=[str(exc)], duration_ms=(time.monotonic() - t0) * 1000)

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(self.connector_id, self.connector_status,
                               last_sync=self._last_sync, last_error=self._last_error,
                               records_synced=self._records_synced, metadata={"error_count": self._error_count})

    async def get_recent_activities(self, limit: int = 20) -> list[dict]:
        """Return the most recent activities."""
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.get(f"{_BASE}/athlete/activities",
                                params={"per_page": limit}, headers=self._headers())
                r.raise_for_status()
                acts = r.json()
                return [{"id": a["id"], "name": a["name"], "type": a["type"],
                         "distance_km": round(a["distance"] / 1000, 2),
                         "duration_min": round(a["moving_time"] / 60, 1),
                         "date": a["start_date_local"]} for a in acts]
        except Exception as exc:
            logger.error("get_recent_activities: %s", exc)
            return []

    async def weekly_stats(self) -> dict[str, Any]:
        """Return athlete weekly totals."""
        try:
            athlete = self._data.get("athlete", {})
            athlete_id = athlete.get("id", "")
            if not athlete_id:
                return {"error": "Connect first"}
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{_BASE}/athletes/{athlete_id}/stats", headers=self._headers())
                r.raise_for_status()
                stats = r.json()
                week = stats.get("recent_run_totals", {})
                return {
                    "runs_this_week": week.get("count", 0),
                    "km_this_week": round(week.get("distance", 0) / 1000, 2),
                    "time_min_this_week": round(week.get("moving_time", 0) / 60, 1),
                }
        except Exception as exc:
            return {"error": str(exc)}

    async def get_fitness_trend(self) -> dict[str, Any]:
        """Return fitness/freshness score from recent YTD stats."""
        try:
            athlete = self._data.get("athlete", {})
            athlete_id = athlete.get("id", "")
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{_BASE}/athletes/{athlete_id}/stats", headers=self._headers())
                r.raise_for_status()
                stats = r.json()
                ytd = stats.get("ytd_run_totals", {})
                return {
                    "ytd_runs": ytd.get("count", 0),
                    "ytd_km": round(ytd.get("distance", 0) / 1000, 2),
                    "ytd_elevation_m": ytd.get("elevation_gain", 0),
                }
        except Exception as exc:
            return {"error": str(exc)}
