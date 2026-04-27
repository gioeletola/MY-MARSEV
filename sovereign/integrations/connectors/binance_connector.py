"""Binance connector — spot/futures portfolio, price feeds, recent trades."""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
import urllib.parse
from typing import Any

import httpx

from .connector_base import ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult

logger = logging.getLogger("connector.binance")
_BASE = "https://api.binance.com"


class BinanceConnector(ConnectorBase):
    connector_id = "binance"
    connector_name = "Binance"
    connector_description = "Binance — spot portfolio, price feeds, order history."
    connector_status = ConnectorStatus.CONNECTED
    requires_oauth = False
    required_scopes: list[str] = []

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._api_key = os.environ.get("BINANCE_API_KEY", "")
        self._api_secret = os.environ.get("BINANCE_API_SECRET", "")
        self._data: dict[str, Any] = {}
        self._error_count = 0

    def _sign(self, params: dict) -> str:
        qs = urllib.parse.urlencode(params)
        return hmac.new(self._api_secret.encode(), qs.encode(), hashlib.sha256).hexdigest()

    async def connect(self) -> bool:
        if not self._api_key or not self._api_secret:
            self._last_error = "BINANCE_API_KEY and BINANCE_API_SECRET required"
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{_BASE}/api/v3/ping")
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
            portfolio = await self.get_portfolio()
            self._data["portfolio"] = portfolio
            self._last_sync = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
            count = len(portfolio.get("balances", []))
            self._records_synced = count
            return SyncResult(self.connector_id, True, count, duration_ms=(time.monotonic() - t0) * 1000)
        except Exception as exc:
            self._last_error = str(exc)
            self._error_count += 1
            return SyncResult(self.connector_id, False, errors=[str(exc)], duration_ms=(time.monotonic() - t0) * 1000)

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(self.connector_id, self.connector_status,
                               last_sync=self._last_sync, last_error=self._last_error,
                               records_synced=self._records_synced, metadata={"error_count": self._error_count})

    async def get_portfolio(self) -> dict[str, Any]:
        """Return spot account balances (non-zero)."""
        params = {"timestamp": int(time.time() * 1000)}
        params["signature"] = self._sign(params)
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{_BASE}/api/v3/account", params=params,
                                headers={"X-MBX-APIKEY": self._api_key})
                r.raise_for_status()
                data = r.json()
                balances = [b for b in data.get("balances", [])
                            if float(b["free"]) > 0 or float(b["locked"]) > 0]
                return {"balances": balances, "canTrade": data.get("canTrade")}
        except Exception as exc:
            return {"error": str(exc)}

    async def get_ticker_price(self, symbol: str = "BTCUSDT") -> dict[str, Any]:
        """Get current ticker price for a symbol."""
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{_BASE}/api/v3/ticker/price", params={"symbol": symbol})
                r.raise_for_status()
                return r.json()
        except Exception as exc:
            return {"error": str(exc)}

    async def get_recent_trades(self, symbol: str = "BTCUSDT", limit: int = 20) -> list[dict]:
        """Get recent trades for a symbol."""
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{_BASE}/api/v3/trades", params={"symbol": symbol, "limit": limit})
                r.raise_for_status()
                return r.json()
        except Exception as exc:
            logger.error("get_recent_trades: %s", exc)
            return []

    async def total_balance_usdt(self) -> float:
        """Approximate total portfolio value in USDT."""
        portfolio = await self.get_portfolio()
        total = 0.0
        for b in portfolio.get("balances", []):
            symbol = b["asset"]
            amount = float(b["free"]) + float(b["locked"])
            if symbol == "USDT":
                total += amount
            else:
                price_data = await self.get_ticker_price(f"{symbol}USDT")
                price = float(price_data.get("price", 0))
                total += amount * price
        return round(total, 2)
