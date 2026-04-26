"""
Revolut Business connector — syncs transactions, balances, and spend analytics.
Auth: Revolut Business API key from config or REVOLUT_API_KEY env var.
Uses Revolut Business API v1 (https://developer.revolut.com/docs/business/business-api).
"""
from __future__ import annotations

import logging
import os
from typing import Any

from sovereign.integrations.connectors.connector_base import (
    ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult,
)

logger = logging.getLogger(__name__)
_API_BASE = "https://b2b.revolut.com/api/1.0"


class RevolutConnector(ConnectorBase):
    connector_id = "revolut"
    connector_name = "Revolut"
    connector_description = (
        "Syncs Revolut Business account balances, recent transactions, "
        "currency exposures, and spend category analytics."
    )
    connector_status = ConnectorStatus.CONNECTED
    requires_oauth = False

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._api_key = (
            self._config.get("api_key")
            or os.getenv("REVOLUT_API_KEY", "")
        )
        # sandbox=True uses sandbox API
        self._sandbox: bool = self._config.get("sandbox", False)
        if self._sandbox:
            self._base = "https://sandbox-b2b.revolut.com/api/1.0"
        else:
            self._base = _API_BASE
        self._data: dict[str, Any] = {}

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def connect(self) -> bool:
        if not self._api_key:
            self._logger.warning("RevolutConnector: no API key configured")
            return False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self._base}/accounts", headers=self._headers())
                if resp.status_code == 200:
                    accounts = resp.json()
                    self._data["accounts"] = accounts
                    self._logger.info("RevolutConnector: connected, %d accounts", len(accounts))
                    return True
                self._logger.warning("Revolut /accounts returned %d", resp.status_code)
                return False
        except Exception as exc:
            self._logger.error("RevolutConnector connect error: %s", exc)
            return False

    async def disconnect(self) -> None:
        self._data.clear()

    async def sync(self) -> SyncResult:
        records = 0
        errors: list[str] = []
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Accounts & balances
                r = await client.get(f"{self._base}/accounts", headers=self._headers())
                if r.status_code == 200:
                    self._data["accounts"] = r.json()
                    records += len(self._data["accounts"])
                else:
                    errors.append(f"accounts: {r.status_code}")

                # Recent transactions (last 30 days)
                from datetime import datetime, timedelta, timezone
                since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
                r2 = await client.get(
                    f"{self._base}/transactions",
                    headers=self._headers(),
                    params={"from": since, "count": 100},
                )
                if r2.status_code == 200:
                    txs = r2.json()
                    self._data["transactions"] = txs
                    records += len(txs)
                else:
                    errors.append(f"transactions: {r2.status_code}")

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
            metadata={"sandbox": self._sandbox, "account_count": len(self._data.get("accounts", []))},
        )

    def get_balances(self) -> list[dict]:
        return [
            {"id": a.get("id"), "name": a.get("name"), "balance": a.get("balance"), "currency": a.get("currency")}
            for a in self._data.get("accounts", [])
        ]

    def get_transactions(self, limit: int = 50) -> list[dict]:
        return self._data.get("transactions", [])[:limit]

    def total_balance_by_currency(self) -> dict[str, float]:
        totals: dict[str, float] = {}
        for acct in self._data.get("accounts", []):
            cur = acct.get("currency", "")
            totals[cur] = totals.get(cur, 0.0) + float(acct.get("balance", 0))
        return totals
