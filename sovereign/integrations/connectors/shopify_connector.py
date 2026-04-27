"""Shopify connector — products, orders, inventory, sales analytics."""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

from .connector_base import ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult

logger = logging.getLogger("connector.shopify")


class ShopifyConnector(ConnectorBase):
    connector_id = "shopify"
    connector_name = "Shopify"
    connector_description = "Shopify Admin API — products, orders, inventory, analytics."
    connector_status = ConnectorStatus.BETA
    requires_oauth = False
    required_scopes: list[str] = []

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._store = os.environ.get("SHOPIFY_STORE_DOMAIN", "")  # e.g. mystore.myshopify.com
        self._token = os.environ.get("SHOPIFY_ACCESS_TOKEN", "")
        self._base = f"https://{self._store}/admin/api/2024-01" if self._store else ""
        self._data: dict[str, Any] = {}
        self._error_count = 0

    def _headers(self) -> dict:
        return {"X-Shopify-Access-Token": self._token, "Content-Type": "application/json"}

    async def connect(self) -> bool:
        if not self._store or not self._token:
            self._last_error = "SHOPIFY_STORE_DOMAIN and SHOPIFY_ACCESS_TOKEN required"
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{self._base}/shop.json", headers=self._headers())
                r.raise_for_status()
                self._data["shop"] = r.json().get("shop", {})
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
            orders = await self.get_recent_orders()
            self._data["orders"] = orders
            self._last_sync = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
            self._records_synced = len(orders)
            return SyncResult(self.connector_id, True, len(orders), duration_ms=(time.monotonic() - t0) * 1000)
        except Exception as exc:
            self._last_error = str(exc)
            self._error_count += 1
            return SyncResult(self.connector_id, False, errors=[str(exc)], duration_ms=(time.monotonic() - t0) * 1000)

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(self.connector_id, self.connector_status,
                               last_sync=self._last_sync, last_error=self._last_error,
                               records_synced=self._records_synced, metadata={"error_count": self._error_count})

    async def get_sales_summary(self, days: int = 30) -> dict[str, Any]:
        """Summarise sales for the past N days."""
        try:
            import datetime
            since = (datetime.datetime.now(datetime.timezone.utc) -
                     datetime.timedelta(days=days)).isoformat()
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.get(f"{self._base}/orders.json",
                                params={"status": "any", "created_at_min": since, "limit": 250},
                                headers=self._headers())
                r.raise_for_status()
                orders = r.json().get("orders", [])
                total = sum(float(o["total_price"]) for o in orders)
                return {"total_revenue": round(total, 2), "order_count": len(orders), "days": days}
        except Exception as exc:
            return {"error": str(exc)}

    async def low_stock_alert(self, threshold: int = 5) -> list[dict]:
        """Return products with inventory below threshold."""
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.get(f"{self._base}/inventory_levels.json",
                                params={"limit": 250}, headers=self._headers())
                r.raise_for_status()
                levels = r.json().get("inventory_levels", [])
                return [item for item in levels if item.get("available", 999) < threshold]
        except Exception as exc:
            logger.error("low_stock_alert: %s", exc)
            return []

    async def get_recent_orders(self, limit: int = 20) -> list[dict]:
        """Return the most recent orders."""
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{self._base}/orders.json",
                                params={"limit": limit, "status": "any"},
                                headers=self._headers())
                r.raise_for_status()
                return r.json().get("orders", [])
        except Exception as exc:
            logger.error("get_recent_orders: %s", exc)
            return []
