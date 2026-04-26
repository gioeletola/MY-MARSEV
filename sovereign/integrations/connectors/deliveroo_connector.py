"""
Deliveroo connector — syncs order history and spending analytics.
Status: BETA — uses Deliveroo's unofficial internal API (requires session cookie).
Config: deliveroo_auth_token from config or DELIVEROO_AUTH_TOKEN env var.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from sovereign.integrations.connectors.connector_base import (
    ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult,
)

logger = logging.getLogger(__name__)
_API_BASE = "https://consumer-ow-api.deliveroo.com/orderapp/v1"


class DeliverooConnector(ConnectorBase):
    connector_id = "deliveroo"
    connector_name = "Deliveroo"
    connector_description = (
        "Syncs Deliveroo order history, spending by restaurant and category, "
        "delivery stats, and favourite restaurants."
    )
    connector_status = ConnectorStatus.BETA
    requires_oauth = False

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._auth_token = self._config.get("auth_token") or os.getenv("DELIVEROO_AUTH_TOKEN", "")
        self._data: dict[str, Any] = {}

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._auth_token}",
            "Accept": "application/json",
            "User-Agent": "Deliveroo/3.0 (iOS; 16.0)",
        }

    async def connect(self) -> bool:
        if not self._auth_token:
            self._logger.warning("DeliverooConnector: no auth token configured")
            return False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{_API_BASE}/customers/me",
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    self._data["customer"] = resp.json()
                    self._logger.info("DeliverooConnector: connected")
                    return True
                return False
        except Exception as exc:
            self._logger.error("DeliverooConnector connect error: %s", exc)
            return False

    async def disconnect(self) -> None:
        self._data.clear()

    async def sync(self) -> SyncResult:
        records = 0
        errors: list[str] = []
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(
                    f"{_API_BASE}/customers/me/orders",
                    headers=self._headers(),
                    params={"page": 1, "per_page": 50},
                )
                if r.status_code == 200:
                    data = r.json()
                    orders = data.get("orders", [])
                    self._data["orders"] = orders
                    records += len(orders)
                    # Compute spend analytics
                    self._data["analytics"] = self._compute_analytics(orders)
                else:
                    errors.append(f"orders: {r.status_code}")
        except Exception as exc:
            errors.append(str(exc))

        result = SyncResult(self.connector_id, not errors, records, errors)
        self._mark_sync(result)
        return result

    def _compute_analytics(self, orders: list[dict]) -> dict[str, Any]:
        total_spend = 0.0
        by_restaurant: dict[str, float] = {}
        for order in orders:
            amount = float(order.get("total_price", {}).get("value", 0)) / 100
            total_spend += amount
            restaurant = order.get("restaurant", {}).get("name", "Unknown")
            by_restaurant[restaurant] = by_restaurant.get(restaurant, 0.0) + amount
        return {
            "total_spend": total_spend,
            "order_count": len(orders),
            "avg_order_value": total_spend / len(orders) if orders else 0.0,
            "top_restaurants": sorted(by_restaurant.items(), key=lambda x: x[1], reverse=True)[:5],
        }

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_id=self.connector_id,
            status=ConnectorStatus.CONNECTED if self._auth_token else ConnectorStatus.DISCONNECTED,
            last_sync=self._last_sync,
            last_error=self._last_error,
            records_synced=self._records_synced,
            metadata=self._data.get("analytics", {}),
        )

    def get_orders(self, limit: int = 20) -> list[dict]:
        return self._data.get("orders", [])[:limit]

    def get_analytics(self) -> dict[str, Any]:
        return self._data.get("analytics", {})
