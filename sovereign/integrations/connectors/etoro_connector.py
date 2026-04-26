"""
eToro connector — syncs portfolio positions, CopyTrader stats, and watchlist.
Auth: eToro username + API key from config or ETORO_USERNAME / ETORO_API_KEY env vars.
Uses eToro's unofficial REST API (read-only portfolio data).
"""
from __future__ import annotations

import logging
import os
from typing import Any

from sovereign.integrations.connectors.connector_base import (
    ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult,
)

logger = logging.getLogger(__name__)
_API_BASE = "https://www.etoro.com/api"


class EToroConnector(ConnectorBase):
    connector_id = "etoro"
    connector_name = "eToro"
    connector_description = (
        "Syncs eToro portfolio positions, CopyTrader allocation, "
        "open trades, P&L, and watchlist instruments."
    )
    connector_status = ConnectorStatus.BETA
    requires_oauth = False

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._username = self._config.get("username") or os.getenv("ETORO_USERNAME", "")
        self._api_key = self._config.get("api_key") or os.getenv("ETORO_API_KEY", "")
        self._data: dict[str, Any] = {}

    def _headers(self) -> dict[str, str]:
        return {
            "AccountType": "Real",
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def connect(self) -> bool:
        if not (self._username and self._api_key):
            self._logger.warning("EToroConnector: username or API key not configured")
            return False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{_API_BASE}/logininfo/v1.1/logindata",
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    self._data["login"] = data
                    self._logger.info("EToroConnector: connected as %s", self._username)
                    return True
                self._logger.warning("eToro logindata returned %d", resp.status_code)
                return False
        except Exception as exc:
            self._logger.error("EToroConnector connect error: %s", exc)
            return False

    async def disconnect(self) -> None:
        self._data.clear()

    async def sync(self) -> SyncResult:
        records = 0
        errors: list[str] = []
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Portfolio
                r = await client.get(
                    f"{_API_BASE}/portfolio/v1/portfolio",
                    headers=self._headers(),
                )
                if r.status_code == 200:
                    portfolio = r.json()
                    self._data["portfolio"] = portfolio
                    positions = portfolio.get("AggregatedPositions", {}).get("InstrumentDisplayData", [])
                    records += len(positions)
                else:
                    errors.append(f"portfolio: {r.status_code}")

                # CopyTrader allocation
                r2 = await client.get(
                    f"{_API_BASE}/copy/v2/copytrades",
                    headers=self._headers(),
                )
                if r2.status_code == 200:
                    copies = r2.json()
                    self._data["copytrades"] = copies
                    records += len(copies.get("data", []))
                else:
                    errors.append(f"copytrades: {r2.status_code}")

        except Exception as exc:
            errors.append(str(exc))

        result = SyncResult(self.connector_id, not errors, records, errors)
        self._mark_sync(result)
        return result

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_id=self.connector_id,
            status=ConnectorStatus.CONNECTED if self._api_key else ConnectorStatus.DISCONNECTED,
            last_sync=self._last_sync,
            last_error=self._last_error,
            records_synced=self._records_synced,
            metadata={"username": self._username},
        )

    def get_positions(self) -> list[dict]:
        portfolio = self._data.get("portfolio", {})
        agg = portfolio.get("AggregatedPositions", {})
        return agg.get("InstrumentDisplayData", [])

    def get_copytrades(self) -> list[dict]:
        return self._data.get("copytrades", {}).get("data", [])

    def total_equity(self) -> float:
        portfolio = self._data.get("portfolio", {})
        return float(portfolio.get("TotalEquity", 0))
