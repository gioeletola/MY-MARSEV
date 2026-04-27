"""Stripe connector — payments, subscriptions, customers, invoices."""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

from .connector_base import ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult

logger = logging.getLogger("connector.stripe")
_BASE = "https://api.stripe.com/v1"


class StripeConnector(ConnectorBase):
    connector_id = "stripe"
    connector_name = "Stripe"
    connector_description = "Stripe — payments, subscriptions, customers, invoices, revenue."
    connector_status = ConnectorStatus.CONNECTED
    requires_oauth = False
    required_scopes: list[str] = []

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._secret_key = os.environ.get("STRIPE_SECRET_KEY", "")
        self._data: dict[str, Any] = {}
        self._error_count = 0

    def _auth(self) -> tuple[str, str]:
        return (self._secret_key, "")

    async def connect(self) -> bool:
        if not self._secret_key:
            self._last_error = "STRIPE_SECRET_KEY required"
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{_BASE}/balance", auth=self._auth())
                r.raise_for_status()
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
            summary = await self.get_revenue_summary()
            self._data["revenue"] = summary
            self._last_sync = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
            self._records_synced = 1
            return SyncResult(self.connector_id, True, 1, duration_ms=(time.monotonic() - t0) * 1000)
        except Exception as exc:
            self._last_error = str(exc)
            self._error_count += 1
            return SyncResult(self.connector_id, False, errors=[str(exc)], duration_ms=(time.monotonic() - t0) * 1000)

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(self.connector_id, self.connector_status,
                               last_sync=self._last_sync, last_error=self._last_error,
                               records_synced=self._records_synced, metadata={"error_count": self._error_count})

    async def get_revenue_summary(self, days: int = 30) -> dict[str, Any]:
        """Summarise charges and revenue for the past N days."""
        try:
            import time as _t
            since = int(_t.time()) - days * 86400
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.get(f"{_BASE}/charges", params={"created[gte]": since, "limit": 100},
                                auth=self._auth())
                r.raise_for_status()
                charges = r.json().get("data", [])
                total = sum(ch["amount"] for ch in charges if ch["status"] == "succeeded") / 100
                return {"total_usd": round(total, 2), "transaction_count": len(charges), "days": days}
        except Exception as exc:
            return {"error": str(exc)}

    async def list_subscriptions(self, status: str = "active") -> list[dict]:
        """List subscriptions by status."""
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{_BASE}/subscriptions", params={"status": status, "limit": 50},
                                auth=self._auth())
                r.raise_for_status()
                return r.json().get("data", [])
        except Exception as exc:
            logger.error("list_subscriptions: %s", exc)
            return []

    async def get_failed_payments(self) -> list[dict]:
        """Return recent failed payment intents."""
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{_BASE}/payment_intents",
                                params={"limit": 20},
                                auth=self._auth())
                r.raise_for_status()
                all_pi = r.json().get("data", [])
                return [p for p in all_pi if p.get("status") in ("requires_payment_method", "canceled")]
        except Exception as exc:
            logger.error("get_failed_payments: %s", exc)
            return []
