"""
Oopbuy connector — syncs orders, parcel tracking, and shopping cart items.
Oopbuy is a Chinese purchasing agent platform (1688/Taobao proxy buyer).
Status: STUB — no public API; uses session-based scraping via configured cookies.
Config: session_cookie from config or OOPBUY_SESSION env var.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from sovereign.integrations.connectors.connector_base import (
    ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult,
)

logger = logging.getLogger(__name__)
_BASE = "https://www.oopbuy.com"


class OopbuyConnector(ConnectorBase):
    connector_id = "oopbuy"
    connector_name = "Oopbuy"
    connector_description = (
        "Syncs Oopbuy purchasing agent orders: item sourcing status, "
        "warehouse arrival, parcel consolidation, and shipping tracking."
    )
    connector_status = ConnectorStatus.BETA
    requires_oauth = False

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._session = self._config.get("session_cookie") or os.getenv("OOPBUY_SESSION", "")
        self._data: dict[str, Any] = {}

    def _headers(self) -> dict[str, str]:
        return {
            "Cookie": f"session={self._session}",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; SOVEREIGN-AI-OS)",
            "Referer": _BASE,
        }

    async def connect(self) -> bool:
        if not self._session:
            self._logger.warning("OopbuyConnector: no session cookie configured")
            return False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{_BASE}/api/user/info", headers=self._headers())
                if resp.status_code == 200:
                    data = resp.json()
                    self._data["user"] = data
                    self._logger.info("OopbuyConnector: connected")
                    return True
                return False
        except Exception as exc:
            self._logger.error("OopbuyConnector connect error: %s", exc)
            return False

    async def disconnect(self) -> None:
        self._data.clear()

    async def sync(self) -> SyncResult:
        records = 0
        errors: list[str] = []

        if not self._session:
            return SyncResult(self.connector_id, False, errors=["No session cookie — configure OOPBUY_SESSION"])

        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Pending orders
                r = await client.get(
                    f"{_BASE}/api/orders",
                    headers=self._headers(),
                    params={"status": "all", "page": 1, "pageSize": 50},
                )
                if r.status_code == 200:
                    data = r.json()
                    orders = data.get("list", data.get("data", []))
                    self._data["orders"] = orders
                    records += len(orders)
                else:
                    errors.append(f"orders: {r.status_code}")

                # Parcels / shipments
                r2 = await client.get(
                    f"{_BASE}/api/parcels",
                    headers=self._headers(),
                    params={"page": 1, "pageSize": 30},
                )
                if r2.status_code == 200:
                    data2 = r2.json()
                    parcels = data2.get("list", data2.get("data", []))
                    self._data["parcels"] = parcels
                    records += len(parcels)
                else:
                    errors.append(f"parcels: {r2.status_code}")

        except Exception as exc:
            errors.append(str(exc))

        result = SyncResult(self.connector_id, not errors, records, errors)
        self._mark_sync(result)
        return result

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_id=self.connector_id,
            status=ConnectorStatus.CONNECTED if self._session else ConnectorStatus.DISCONNECTED,
            last_sync=self._last_sync,
            last_error=self._last_error,
            records_synced=self._records_synced,
            metadata={
                "order_count": len(self._data.get("orders", [])),
                "parcel_count": len(self._data.get("parcels", [])),
                "note": "Stub connector — requires valid Oopbuy session cookie",
            },
        )

    def get_orders(self) -> list[dict]:
        return self._data.get("orders", [])

    def get_parcels(self) -> list[dict]:
        return self._data.get("parcels", [])

    def pending_arrivals(self) -> list[dict]:
        """Orders awaiting warehouse arrival."""
        return [
            o for o in self._data.get("orders", [])
            if o.get("status") in ("purchased", "warehouse_pending", "in_transit")
        ]
