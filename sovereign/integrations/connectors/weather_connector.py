"""
Weather connector — fetches current weather and forecast via Open-Meteo (free, no API key).
"""
from __future__ import annotations

import logging
from typing import Any

from sovereign.integrations.connectors.connector_base import (
    ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult,
)

logger = logging.getLogger(__name__)

_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
_WEATHER_URL = "https://api.open-meteo.com/v1/forecast"


class WeatherConnector(ConnectorBase):
    connector_id = "weather"
    connector_name = "Weather"
    connector_description = "Current weather and 7-day forecast via Open-Meteo (no API key required)."
    connector_status = ConnectorStatus.CONNECTED
    requires_oauth = False

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._location = self._config.get("location", "Milan")
        self._latitude: float | None = self._config.get("latitude")
        self._longitude: float | None = self._config.get("longitude")
        self._weather_data: dict[str, Any] = {}

    async def connect(self) -> bool:
        if self._latitude is None or self._longitude is None:
            return await self._geocode(self._location)
        return True

    async def _geocode(self, location: str) -> bool:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(_GEOCODE_URL, params={"name": location, "count": 1})
                if resp.status_code == 200:
                    results = resp.json().get("results", [])
                    if results:
                        self._latitude = results[0]["latitude"]
                        self._longitude = results[0]["longitude"]
                        self._location = results[0]["name"]
                        return True
        except Exception as exc:
            self._logger.error("WeatherConnector: geocode failed: %s", exc)
        return False

    async def disconnect(self) -> None:
        self._weather_data = {}

    async def sync(self) -> SyncResult:
        if self._latitude is None:
            ok = await self.connect()
            if not ok:
                return SyncResult(connector_id=self.connector_id, success=False, errors=["Geocode failed"])
        try:
            import httpx
            params = {
                "latitude": str(self._latitude),
                "longitude": str(self._longitude),
                "current": "temperature_2m,weathercode,windspeed_10m,precipitation",
                "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_sum",
                "timezone": "auto",
                "forecast_days": "7",
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(_WEATHER_URL, params=params)
                if resp.status_code == 200:
                    self._weather_data = resp.json()
                    self._weather_data["_location"] = self._location
                    return SyncResult(connector_id=self.connector_id, success=True, records_synced=1)
                return SyncResult(
                    connector_id=self.connector_id, success=False,
                    errors=[f"HTTP {resp.status_code}"],
                )
        except Exception as exc:
            return SyncResult(connector_id=self.connector_id, success=False, errors=[str(exc)])

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_id=self.connector_id,
            status=self.connector_status,
            last_sync=self._last_sync,
            last_error=self._last_error,
            metadata={"location": self._location, "coords": f"{self._latitude},{self._longitude}"},
        )

    def get_current(self) -> dict[str, Any]:
        return self._weather_data.get("current", {})

    def get_forecast(self) -> dict[str, Any]:
        return self._weather_data.get("daily", {})
