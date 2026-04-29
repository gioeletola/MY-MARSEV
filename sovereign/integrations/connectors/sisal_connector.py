"""Sisal connector — lottery results, ticket checking, betting account balance."""
from __future__ import annotations

import logging
import os
import time
from typing import Any


from .connector_base import ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult

logger = logging.getLogger("connector.sisal")


class SisalConnector(ConnectorBase):
    connector_id = "sisal"
    connector_name = "Sisal"
    connector_description = "Sisal — lottery results, ticket checking, account balance."
    connector_status = ConnectorStatus.BETA
    requires_oauth = False
    required_scopes: list[str] = []

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._session_token = os.environ.get("SISAL_SESSION_TOKEN", "")
        self._data: dict[str, Any] = {}
        self._error_count = 0

    async def connect(self) -> bool:
        if not self._session_token:
            self._last_error = "SISAL_SESSION_TOKEN required (stub mode)"
            return False
        self._data["connected"] = True
        return True

    async def disconnect(self) -> None:
        self._data = {}

    async def sync(self) -> SyncResult:
        t0 = time.monotonic()
        self._last_sync = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        return SyncResult(self.connector_id, True, 0, duration_ms=(time.monotonic() - t0) * 1000)

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(self.connector_id, self.connector_status,
                               last_sync=self._last_sync, last_error=self._last_error,
                               metadata={"error_count": self._error_count, "note": "stub"})

    async def get_recent_results(self, game: str = "superenalotto") -> dict[str, Any]:
        """Return cached lottery results (stub)."""
        return {"game": game, "numbers": [], "note": "stub — set SISAL_SESSION_TOKEN"}

    async def check_ticket(self, ticket_code: str) -> dict[str, Any]:
        """Check ticket status (stub)."""
        return {"ticket_code": ticket_code, "status": "stub", "prize": None}

    async def get_account_balance(self) -> dict[str, Any]:
        """Return betting account balance (stub)."""
        return {"balance_eur": 0.0, "note": "stub"}
