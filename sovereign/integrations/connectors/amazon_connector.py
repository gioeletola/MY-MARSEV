"""
Amazon connector — syncs order history, wishlist, and spending analytics.
Auth: Amazon SP-API (for sellers) or unofficial order history endpoint.
Config: access_key, secret_key, refresh_token, marketplace_id
or AMAZON_ACCESS_KEY / AMAZON_SECRET_KEY / AMAZON_REFRESH_TOKEN env vars.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from sovereign.integrations.connectors.connector_base import (
    ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult,
)

logger = logging.getLogger(__name__)


class AmazonConnector(ConnectorBase):
    connector_id = "amazon"
    connector_name = "Amazon"
    connector_description = (
        "Syncs Amazon order history, spending by category, wishlist items, "
        "and (for sellers) SP-API inventory and sales data."
    )
    connector_status = ConnectorStatus.BETA
    requires_oauth = True
    required_scopes = ["sellingpartnerapi::orders", "sellingpartnerapi::catalog_items"]

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._access_key = self._config.get("access_key") or os.getenv("AMAZON_ACCESS_KEY", "")
        self._secret_key = self._config.get("secret_key") or os.getenv("AMAZON_SECRET_KEY", "")
        self._refresh_token = self._config.get("refresh_token") or os.getenv("AMAZON_REFRESH_TOKEN", "")
        self._marketplace = self._config.get("marketplace_id") or os.getenv("AMAZON_MARKETPLACE_ID", "ATVPDKIKX0DER")
        self._access_token: str = ""
        self._data: dict[str, Any] = {}

    async def _refresh_access_token(self) -> bool:
        """Exchange refresh token for access token via LWA."""
        if not self._refresh_token:
            return False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://api.amazon.com/auth/o2/token",
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": self._refresh_token,
                        "client_id": self._config.get("client_id", ""),
                        "client_secret": self._config.get("client_secret", ""),
                    },
                )
                if resp.status_code == 200:
                    self._access_token = resp.json().get("access_token", "")
                    return bool(self._access_token)
                return False
        except Exception as exc:
            self._logger.error("AmazonConnector token refresh error: %s", exc)
            return False

    async def connect(self) -> bool:
        if not self._refresh_token:
            self._logger.warning("AmazonConnector: no refresh token configured")
            return False
        ok = await self._refresh_access_token()
        if ok:
            self._logger.info("AmazonConnector: access token obtained")
        return ok

    async def disconnect(self) -> None:
        self._access_token = ""
        self._data.clear()

    async def sync(self) -> SyncResult:
        records = 0
        errors: list[str] = []

        if not self._access_token:
            ok = await self._refresh_access_token()
            if not ok:
                return SyncResult(self.connector_id, False, errors=["No access token"])

        try:
            import httpx
            from datetime import datetime, timedelta, timezone
            since = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
            headers = {
                "x-amz-access-token": self._access_token,
                "Content-Type": "application/json",
            }
            async with httpx.AsyncClient(timeout=20.0) as client:
                r = await client.get(
                    "https://sellingpartnerapi-na.amazon.com/orders/v0/orders",
                    headers=headers,
                    params={
                        "MarketplaceIds": self._marketplace,
                        "CreatedAfter": since,
                        "MaxResultsPerPage": 100,
                    },
                )
                if r.status_code == 200:
                    orders = r.json().get("payload", {}).get("Orders", [])
                    self._data["orders"] = orders
                    records += len(orders)
                else:
                    errors.append(f"orders: {r.status_code} {r.text[:100]}")

        except Exception as exc:
            errors.append(str(exc))

        result = SyncResult(self.connector_id, not errors, records, errors)
        self._mark_sync(result)
        return result

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_id=self.connector_id,
            status=ConnectorStatus.CONNECTED if self._access_token else ConnectorStatus.DISCONNECTED,
            last_sync=self._last_sync,
            last_error=self._last_error,
            records_synced=self._records_synced,
            metadata={"marketplace_id": self._marketplace, "order_count": len(self._data.get("orders", []))},
        )

    def get_orders(self, limit: int = 50) -> list[dict]:
        return self._data.get("orders", [])[:limit]

    def total_spend(self) -> float:
        return sum(
            float(o.get("OrderTotal", {}).get("Amount", 0))
            for o in self._data.get("orders", [])
        )
