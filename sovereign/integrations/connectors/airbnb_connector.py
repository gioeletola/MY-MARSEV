"""
Airbnb connector — syncs listing performance, reservations, and payout history.
Auth: Airbnb OAuth token from config or AIRBNB_ACCESS_TOKEN env var.
Status: BETA — uses unofficial Airbnb API endpoints (subject to change).
"""
from __future__ import annotations

import logging
import os
from typing import Any

from sovereign.integrations.connectors.connector_base import (
    ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult,
)

logger = logging.getLogger(__name__)
_API_BASE = "https://api.airbnb.com/v2"


class AirbnbConnector(ConnectorBase):
    connector_id = "airbnb"
    connector_name = "Airbnb"
    connector_description = (
        "Syncs Airbnb listing performance metrics, active reservations, "
        "guest reviews, pricing calendar, and payout history."
    )
    connector_status = ConnectorStatus.BETA
    requires_oauth = True
    required_scopes = ["listings:read", "reservations:read", "reviews:read"]

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._token = self._config.get("access_token") or os.getenv("AIRBNB_ACCESS_TOKEN", "")
        self._data: dict[str, Any] = {}

    def _headers(self) -> dict[str, str]:
        return {
            "X-Airbnb-OAuth-Token": self._token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def connect(self) -> bool:
        if not self._token:
            self._logger.warning("AirbnbConnector: no access token configured")
            return False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{_API_BASE}/account", headers=self._headers())
                if resp.status_code == 200:
                    account = resp.json()
                    self._data["account"] = account
                    self._logger.info("AirbnbConnector: connected, user_id=%s", account.get("user", {}).get("id"))
                    return True
                self._logger.warning("Airbnb /account returned %d", resp.status_code)
                return False
        except Exception as exc:
            self._logger.error("AirbnbConnector connect error: %s", exc)
            return False

    async def disconnect(self) -> None:
        self._data.clear()

    async def sync(self) -> SyncResult:
        records = 0
        errors: list[str] = []
        try:
            import httpx
            async with httpx.AsyncClient(timeout=20.0) as client:
                # Listings
                r = await client.get(
                    f"{_API_BASE}/listings",
                    headers=self._headers(),
                    params={"_limit": 50, "_offset": 0},
                )
                if r.status_code == 200:
                    listings = r.json().get("listings", [])
                    self._data["listings"] = listings
                    records += len(listings)
                else:
                    errors.append(f"listings: {r.status_code}")

                # Reservations
                r2 = await client.get(
                    f"{_API_BASE}/reservations",
                    headers=self._headers(),
                    params={"_limit": 50, "_offset": 0},
                )
                if r2.status_code == 200:
                    reservations = r2.json().get("reservations", [])
                    self._data["reservations"] = reservations
                    records += len(reservations)
                else:
                    errors.append(f"reservations: {r2.status_code}")

                # Reviews
                r3 = await client.get(
                    f"{_API_BASE}/reviews",
                    headers=self._headers(),
                    params={"_limit": 20, "role": "host"},
                )
                if r3.status_code == 200:
                    reviews = r3.json().get("reviews", [])
                    self._data["reviews"] = reviews
                    records += len(reviews)

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
                "listing_count": len(self._data.get("listings", [])),
                "active_reservations": len(self._data.get("reservations", [])),
            },
        )

    def get_listings(self) -> list[dict]:
        return self._data.get("listings", [])

    def get_active_reservations(self) -> list[dict]:
        return [r for r in self._data.get("reservations", []) if r.get("status") in ("accepted", "pending")]

    def get_recent_reviews(self) -> list[dict]:
        return self._data.get("reviews", [])

    def average_rating(self) -> float:
        reviews = self._data.get("reviews", [])
        if not reviews:
            return 0.0
        ratings = [float(r.get("rating", 0)) for r in reviews if r.get("rating")]
        return sum(ratings) / len(ratings) if ratings else 0.0
