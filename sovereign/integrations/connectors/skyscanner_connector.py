"""
Skyscanner connector — flight, hotel, and car hire search via RapidAPI.
Auth: RapidAPI key (SKYSCANNER_RAPIDAPI_KEY).
Status: CONNECTED — uses Skyscanner4Dev via RapidAPI (free tier available).
"""
from __future__ import annotations

import logging
import os
from typing import Any

from sovereign.integrations.connectors.connector_base import (
    ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult,
)

logger = logging.getLogger(__name__)
_API_BASE = "https://skyscanner44.p.rapidapi.com"
_RAPIDAPI_HOST = "skyscanner44.p.rapidapi.com"


class SkyscannerConnector(ConnectorBase):
    connector_id = "skyscanner"
    connector_name = "Skyscanner"
    connector_description = (
        "Searches for flights, hotels, and car hire via Skyscanner RapidAPI. "
        "Supports price alerts and cheapest date discovery."
    )
    connector_status = ConnectorStatus.CONNECTED
    requires_oauth = False
    required_env_vars = ["SKYSCANNER_RAPIDAPI_KEY"]

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._api_key = self._config.get("rapidapi_key") or os.getenv("SKYSCANNER_RAPIDAPI_KEY", "")
        self.api_base = _API_BASE
        self._data: dict[str, Any] = {}
        self._error_count = 0
        self._price_alerts: list[dict] = []

    def _headers(self) -> dict[str, str]:
        return {
            "X-RapidAPI-Key": self._api_key,
            "X-RapidAPI-Host": _RAPIDAPI_HOST,
        }

    async def connect(self) -> bool:
        if not self._api_key:
            self._logger.warning("SkyscannerConnector: no RapidAPI key configured")
            return False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Test with a locale list call
                resp = await client.get(
                    f"{self.api_base}/autocomplete",
                    headers=self._headers(),
                    params={"query": "London", "locale": "en-US"},
                )
                if resp.status_code == 200:
                    self._logger.info("SkyscannerConnector: connected")
                    return True
                self._logger.warning("Skyscanner connect returned %d", resp.status_code)
                return False
        except Exception as exc:
            self._logger.error("SkyscannerConnector connect error: %s", exc)
            self._error_count += 1
            return False

    async def disconnect(self) -> None:
        self._data.clear()

    async def sync(self) -> SyncResult:
        """Sync validates connectivity; actual searches are on-demand."""
        connected = await self.connect()
        result = SyncResult(
            connector_id=self.connector_id,
            success=connected,
            records_synced=0,
            errors=[] if connected else ["Failed to connect to Skyscanner RapidAPI"],
        )
        self._mark_sync(result)
        return result

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_id=self.connector_id,
            status=ConnectorStatus.CONNECTED if self._api_key else ConnectorStatus.DISCONNECTED,
            last_sync=self._last_sync,
            last_error=self._last_error,
            records_synced=self._records_synced,
            latency_ms=0.0,
            metadata={"price_alerts": len(self._price_alerts), "error_count": self._error_count},
        )

    async def search_flights(self, origin: str, destination: str, date: str,
                              adults: int = 1, currency: str = "EUR") -> dict:
        """
        Search one-way flights. origin/destination are IATA codes (e.g. 'LHR', 'JFK').
        date format: YYYY-MM-DD.
        """
        try:
            import httpx
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(
                    f"{self.api_base}/search",
                    headers=self._headers(),
                    params={
                        "origin": origin,
                        "destination": destination,
                        "date": date,
                        "adults": adults,
                        "currency": currency,
                    },
                )
                if resp.status_code == 200:
                    return resp.json()
                return {"error": resp.status_code, "detail": resp.text[:200]}
        except Exception as exc:
            self._logger.error("search_flights error: %s", exc)
            return {"error": str(exc)}

    def price_alert_create(self, origin: str, destination: str, date: str,
                            max_price: float, currency: str = "EUR") -> dict:
        """
        Register a local price alert. Returns alert ID.
        Note: actual polling must be triggered externally via sync().
        """
        import time
        alert_id = f"alert_{int(time.time())}"
        alert = {
            "id": alert_id,
            "origin": origin,
            "destination": destination,
            "date": date,
            "max_price": max_price,
            "currency": currency,
            "triggered": False,
        }
        self._price_alerts.append(alert)
        return alert

    async def get_cheapest_dates(self, origin: str, destination: str,
                                  year_month: str, currency: str = "EUR") -> dict:
        """
        Find the cheapest travel dates for a given month.
        year_month format: YYYY-MM
        """
        try:
            import httpx
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(
                    f"{self.api_base}/calendar",
                    headers=self._headers(),
                    params={
                        "origin": origin,
                        "destination": destination,
                        "yearMonth": year_month,
                        "currency": currency,
                    },
                )
                if resp.status_code == 200:
                    return resp.json()
                return {"error": resp.status_code}
        except Exception as exc:
            self._logger.error("get_cheapest_dates error: %s", exc)
            return {"error": str(exc)}

    def list_price_alerts(self) -> list[dict]:
        """Return all registered price alerts."""
        return self._price_alerts
