"""
MetaTrader connector — syncs open positions, trade history, and account equity.

Supports MetaTrader 4 and MetaTrader 5 via the MT Manager REST bridge
(https://github.com/khramykh/mt-manager) or a custom local bridge.
Config: mt_host, mt_port, mt_login, mt_password, mt_server
"""
from __future__ import annotations

import logging
import os
from typing import Any

from sovereign.integrations.connectors.connector_base import (
    ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult,
)

logger = logging.getLogger(__name__)


class MetaTraderConnector(ConnectorBase):
    connector_id = "metatrader"
    connector_name = "MetaTrader"
    connector_description = (
        "Syncs MetaTrader 4/5 account equity, open positions, trade history, "
        "margin level, and P&L attribution."
    )
    connector_status = ConnectorStatus.BETA
    requires_oauth = False

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._host = self._config.get("mt_host") or os.getenv("MT_HOST", "127.0.0.1")
        self._port = int(self._config.get("mt_port") or os.getenv("MT_PORT", "8080"))
        self._login = self._config.get("mt_login") or os.getenv("MT_LOGIN", "")
        self._password = self._config.get("mt_password") or os.getenv("MT_PASSWORD", "")
        self._server = self._config.get("mt_server") or os.getenv("MT_SERVER", "")
        self._base_url = f"http://{self._host}:{self._port}"
        self._data: dict[str, Any] = {}
        self._connected: bool = False

    async def connect(self) -> bool:
        if not self._login:
            self._logger.warning("MetaTraderConnector: no login configured")
            return False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self._base_url}/connect",
                    json={"login": self._login, "password": self._password, "server": self._server},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    self._connected = data.get("connected", False)
                    self._data["account"] = data.get("account", {})
                    self._logger.info("MetaTraderConnector: connected, equity=%.2f", self._data["account"].get("equity", 0))
                    return self._connected
                return False
        except Exception as exc:
            self._logger.error("MetaTraderConnector connect error: %s", exc)
            return False

    async def disconnect(self) -> None:
        self._connected = False
        self._data.clear()
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(f"{self._base_url}/disconnect")
        except Exception:
            pass

    async def sync(self) -> SyncResult:
        records = 0
        errors: list[str] = []
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Account summary
                r = await client.get(f"{self._base_url}/account")
                if r.status_code == 200:
                    self._data["account"] = r.json()
                    records += 1
                else:
                    errors.append(f"account: {r.status_code}")

                # Open positions
                r2 = await client.get(f"{self._base_url}/positions")
                if r2.status_code == 200:
                    positions = r2.json()
                    self._data["positions"] = positions
                    records += len(positions)
                else:
                    errors.append(f"positions: {r2.status_code}")

                # Trade history (last 100)
                r3 = await client.get(f"{self._base_url}/history", params={"count": 100})
                if r3.status_code == 200:
                    trades = r3.json()
                    self._data["history"] = trades
                    records += len(trades)
                else:
                    errors.append(f"history: {r3.status_code}")

        except Exception as exc:
            errors.append(str(exc))

        result = SyncResult(self.connector_id, not errors, records, errors)
        self._mark_sync(result)
        return result

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_id=self.connector_id,
            status=ConnectorStatus.CONNECTED if self._connected else ConnectorStatus.DISCONNECTED,
            last_sync=self._last_sync,
            last_error=self._last_error,
            records_synced=self._records_synced,
            metadata={
                "equity": self._data.get("account", {}).get("equity", 0),
                "open_positions": len(self._data.get("positions", [])),
                "server": self._server,
            },
        )

    def get_account_summary(self) -> dict[str, Any]:
        return self._data.get("account", {})

    def get_open_positions(self) -> list[dict]:
        return self._data.get("positions", [])

    def get_trade_history(self, limit: int = 50) -> list[dict]:
        return self._data.get("history", [])[:limit]

    def total_pnl(self) -> float:
        return sum(float(p.get("profit", 0)) for p in self._data.get("positions", []))
