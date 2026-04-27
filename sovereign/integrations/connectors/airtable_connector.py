"""Airtable connector — bases, tables, records, views, automations."""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

from .connector_base import ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult

logger = logging.getLogger("connector.airtable")
_BASE = "https://api.airtable.com/v0"


class AirtableConnector(ConnectorBase):
    connector_id = "airtable"
    connector_name = "Airtable"
    connector_description = "Airtable REST API — bases, tables, records, views."
    connector_status = ConnectorStatus.CONNECTED
    requires_oauth = False
    required_scopes: list[str] = []

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._token = os.environ.get("AIRTABLE_API_KEY", "")
        self._base_id = os.environ.get("AIRTABLE_BASE_ID", "")
        self._data: dict[str, Any] = {}
        self._error_count = 0

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"}

    async def connect(self) -> bool:
        if not self._token or not self._base_id:
            self._last_error = "AIRTABLE_API_KEY and AIRTABLE_BASE_ID required"
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"https://api.airtable.com/v0/meta/bases/{self._base_id}/tables",
                                headers=self._headers())
                r.raise_for_status()
                self._data["tables"] = [t["name"] for t in r.json().get("tables", [])]
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
            self._last_sync = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
            count = len(self._data.get("tables", []))
            return SyncResult(self.connector_id, True, count, duration_ms=(time.monotonic() - t0) * 1000)
        except Exception as exc:
            self._last_error = str(exc)
            return SyncResult(self.connector_id, False, errors=[str(exc)], duration_ms=(time.monotonic() - t0) * 1000)

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(self.connector_id, self.connector_status,
                               last_sync=self._last_sync, last_error=self._last_error,
                               records_synced=self._records_synced, metadata={"error_count": self._error_count})

    async def get_table_records(self, table: str, view: str | None = None,
                                max_records: int = 100) -> list[dict]:
        """Fetch records from a table, optionally filtered by view."""
        params: dict[str, Any] = {"maxRecords": max_records}
        if view:
            params["view"] = view
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.get(f"{_BASE}/{self._base_id}/{table}", params=params,
                                headers=self._headers())
                r.raise_for_status()
                return r.json().get("records", [])
        except Exception as exc:
            logger.error("get_table_records: %s", exc)
            return []

    async def create_record(self, table: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Create a new record in a table."""
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.post(f"{_BASE}/{self._base_id}/{table}",
                                 json={"fields": fields}, headers={**self._headers(),
                                                                    "Content-Type": "application/json"})
                r.raise_for_status()
                return r.json()
        except Exception as exc:
            return {"error": str(exc)}

    async def update_record(self, table: str, record_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Update an existing record (PATCH — only sends changed fields)."""
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.patch(f"{_BASE}/{self._base_id}/{table}/{record_id}",
                                  json={"fields": fields}, headers={**self._headers(),
                                                                     "Content-Type": "application/json"})
                r.raise_for_status()
                return r.json()
        except Exception as exc:
            return {"error": str(exc)}
