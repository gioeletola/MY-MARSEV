"""
Uber connector — ride history, spend analytics, and ride scheduling via Uber API.
Auth: OAuth2 (UBER_ACCESS_TOKEN, UBER_CLIENT_ID, UBER_CLIENT_SECRET).
Status: BETA — requires Uber developer app approval for trip history scope.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from sovereign.integrations.connectors.connector_base import (
    ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult,
)

logger = logging.getLogger(__name__)
_API_BASE = "https://api.uber.com/v1.2"


class UberConnector(ConnectorBase):
    connector_id = "uber"
    connector_name = "Uber"
    connector_description = (
        "Connects to Uber via Rides API. Syncs trip history, spend analytics, "
        "and supports ride scheduling."
    )
    connector_status = ConnectorStatus.BETA
    requires_oauth = True
    required_env_vars = ["UBER_ACCESS_TOKEN", "UBER_CLIENT_ID"]

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._access_token = self._config.get("access_token") or os.getenv("UBER_ACCESS_TOKEN", "")
        self._client_id = self._config.get("client_id") or os.getenv("UBER_CLIENT_ID", "")
        self.api_base = _API_BASE
        self._data: dict[str, Any] = {}
        self._error_count = 0

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Accept-Language": "en_US",
            "Content-Type": "application/json",
        }

    async def connect(self) -> bool:
        if not self._access_token:
            self._logger.warning("UberConnector: no access token configured")
            return False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.api_base}/me", headers=self._headers())
                if resp.status_code == 200:
                    self._data["profile"] = resp.json()
                    self._logger.info("UberConnector: connected as %s", self._data["profile"].get("first_name"))
                    return True
                self._logger.warning("Uber /me returned %d", resp.status_code)
                return False
        except Exception as exc:
            self._logger.error("UberConnector connect error: %s", exc)
            self._error_count += 1
            return False

    async def disconnect(self) -> None:
        self._data.clear()

    async def sync(self) -> SyncResult:
        records = 0
        errors: list[str] = []
        try:
            import httpx
            async with httpx.AsyncClient(timeout=20.0) as client:
                # Profile
                r = await client.get(f"{self.api_base}/me", headers=self._headers())
                if r.status_code == 200:
                    self._data["profile"] = r.json()
                    records += 1
                else:
                    errors.append(f"profile: {r.status_code}")

                # Trip history
                r2 = await client.get(
                    f"{self.api_base}/history",
                    headers=self._headers(),
                    params={"limit": 50, "offset": 0},
                )
                if r2.status_code == 200:
                    history = r2.json()
                    self._data["trips"] = history.get("history", [])
                    records += len(self._data["trips"])
                else:
                    errors.append(f"trip_history: {r2.status_code}")

        except Exception as exc:
            errors.append(str(exc))
            self._error_count += 1

        result = SyncResult(self.connector_id, not errors, records, errors)
        self._mark_sync(result)
        return result

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_id=self.connector_id,
            status=ConnectorStatus.BETA if self._access_token else ConnectorStatus.DISCONNECTED,
            last_sync=self._last_sync,
            last_error=self._last_error,
            records_synced=self._records_synced,
            latency_ms=0.0,
            metadata={"trip_count": len(self._data.get("trips", [])), "error_count": self._error_count},
        )

    async def get_ride_history(self, limit: int = 50) -> list[dict]:
        """Fetch ride history from Uber API."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.api_base}/history",
                    headers=self._headers(),
                    params={"limit": limit, "offset": 0},
                )
                if resp.status_code == 200:
                    trips = resp.json().get("history", [])
                    self._data["trips"] = trips
                    return trips
                return []
        except Exception as exc:
            self._logger.error("get_ride_history error: %s", exc)
            return []

    def total_spend(self, currency: str = "USD") -> dict:
        """Calculate total spend from cached trip history."""
        trips = self._data.get("trips", [])
        total = 0.0
        count = 0
        for trip in trips:
            fare = trip.get("fare", {})
            if fare and fare.get("currency_code", "") == currency:
                total += float(fare.get("value", 0))
                count += 1
        return {"total_spend": round(total, 2), "currency": currency, "trip_count": count}

    async def request_ride(self, start_latitude: float, start_longitude: float,
                           end_latitude: float, end_longitude: float,
                           product_id: str = "") -> dict:
        """
        Request a ride (requires ride.request scope).
        product_id can be retrieved from /products endpoint.
        """
        try:
            import httpx
            payload: dict[str, Any] = {
                "start_latitude": start_latitude,
                "start_longitude": start_longitude,
                "end_latitude": end_latitude,
                "end_longitude": end_longitude,
            }
            if product_id:
                payload["product_id"] = product_id
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.api_base}/requests",
                    headers=self._headers(),
                    json=payload,
                )
                return resp.json()
        except Exception as exc:
            self._logger.error("request_ride error: %s", exc)
            return {"error": str(exc)}

    def get_cached_trips(self, limit: int = 20) -> list[dict]:
        """Return cached trip history."""
        return self._data.get("trips", [])[:limit]
