"""CoinGecko connector — coin prices, market data, portfolio tracking (free API)."""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from .connector_base import ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult

logger = logging.getLogger("connector.coingecko")
_BASE = "https://api.coingecko.com/api/v3"


class CoinGeckoConnector(ConnectorBase):
    connector_id = "coingecko"
    connector_name = "CoinGecko"
    connector_description = "CoinGecko free API — coin prices, market cap, portfolio value."
    connector_status = ConnectorStatus.CONNECTED
    requires_oauth = False
    required_scopes: list[str] = []

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._portfolio: dict[str, float] = {}  # coin_id → amount held
        self._data: dict[str, Any] = {}
        self._error_count = 0

    def set_portfolio(self, holdings: dict[str, float]) -> None:
        """Configure holdings: {"bitcoin": 0.5, "ethereum": 2.0}."""
        self._portfolio = holdings

    async def connect(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{_BASE}/ping")
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
            overview = await self.get_market_overview()
            self._data["market"] = overview
            self._last_sync = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
            self._records_synced = len(overview)
            return SyncResult(self.connector_id, True, len(overview), duration_ms=(time.monotonic() - t0) * 1000)
        except Exception as exc:
            self._last_error = str(exc)
            self._error_count += 1
            return SyncResult(self.connector_id, False, errors=[str(exc)], duration_ms=(time.monotonic() - t0) * 1000)

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(self.connector_id, self.connector_status,
                               last_sync=self._last_sync, last_error=self._last_error,
                               records_synced=self._records_synced, metadata={"error_count": self._error_count})

    async def get_price(self, coins: list[str], vs: str = "usd") -> dict[str, Any]:
        """Get current prices for a list of coin IDs."""
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{_BASE}/simple/price",
                                params={"ids": ",".join(coins), "vs_currencies": vs,
                                        "include_24hr_change": "true"})
                r.raise_for_status()
                return r.json()
        except Exception as exc:
            return {"error": str(exc)}

    async def get_market_overview(self, limit: int = 20) -> list[dict]:
        """Return top coins by market cap."""
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.get(f"{_BASE}/coins/markets",
                                params={"vs_currency": "usd", "order": "market_cap_desc",
                                        "per_page": limit, "page": 1})
                r.raise_for_status()
                return [{"id": c["id"], "symbol": c["symbol"], "name": c["name"],
                         "price_usd": c["current_price"],
                         "change_24h_pct": c["price_change_percentage_24h"],
                         "market_cap_usd": c["market_cap"]} for c in r.json()]
        except Exception as exc:
            logger.error("get_market_overview: %s", exc)
            return []

    async def get_portfolio_value(self, vs: str = "usd") -> dict[str, Any]:
        """Calculate total portfolio value in the given currency."""
        if not self._portfolio:
            return {"total": 0.0, "note": "Call set_portfolio() first"}
        prices = await self.get_price(list(self._portfolio.keys()), vs=vs)
        total = 0.0
        breakdown = {}
        for coin, amount in self._portfolio.items():
            price = prices.get(coin, {}).get(vs, 0)
            value = price * amount
            breakdown[coin] = {"amount": amount, "price": price, "value": round(value, 2)}
            total += value
        return {"total": round(total, 2), "currency": vs, "breakdown": breakdown}
