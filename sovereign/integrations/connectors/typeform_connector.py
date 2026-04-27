"""Typeform connector — forms, responses, analytics, export."""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

from .connector_base import ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult

logger = logging.getLogger("connector.typeform")
_BASE = "https://api.typeform.com"


class TypeformConnector(ConnectorBase):
    connector_id = "typeform"
    connector_name = "Typeform"
    connector_description = "Typeform API — forms, responses, completion rates."
    connector_status = ConnectorStatus.CONNECTED
    requires_oauth = False
    required_scopes: list[str] = []

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._token = os.environ.get("TYPEFORM_API_KEY", "")
        self._data: dict[str, Any] = {}
        self._error_count = 0

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"}

    async def connect(self) -> bool:
        if not self._token:
            self._last_error = "TYPEFORM_API_KEY required"
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{_BASE}/me", headers=self._headers())
                r.raise_for_status()
                self._data["me"] = r.json()
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
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{_BASE}/forms", params={"page_size": 10}, headers=self._headers())
                r.raise_for_status()
                forms = r.json().get("items", [])
                self._data["forms"] = forms
                self._last_sync = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
                self._records_synced = len(forms)
                return SyncResult(self.connector_id, True, len(forms), duration_ms=(time.monotonic() - t0) * 1000)
        except Exception as exc:
            self._last_error = str(exc)
            self._error_count += 1
            return SyncResult(self.connector_id, False, errors=[str(exc)], duration_ms=(time.monotonic() - t0) * 1000)

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(self.connector_id, self.connector_status,
                               last_sync=self._last_sync, last_error=self._last_error,
                               records_synced=self._records_synced, metadata={"error_count": self._error_count})

    async def get_form_responses(self, form_id: str, page_size: int = 25) -> list[dict]:
        """Fetch responses for a specific form."""
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.get(f"{_BASE}/forms/{form_id}/responses",
                                params={"page_size": page_size}, headers=self._headers())
                r.raise_for_status()
                return r.json().get("items", [])
        except Exception as exc:
            logger.error("get_form_responses: %s", exc)
            return []

    async def get_completion_rate(self, form_id: str) -> dict[str, Any]:
        """Return form completion rate."""
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{_BASE}/forms/{form_id}/insights/summary", headers=self._headers())
                r.raise_for_status()
                data = r.json()
                return {
                    "responses": data.get("responses_count", 0),
                    "completion_rate": data.get("completion_rate", 0),
                }
        except Exception as exc:
            return {"error": str(exc)}

    async def export_responses(self, form_id: str) -> list[dict]:
        """Export all responses for a form (paginated)."""
        results = []
        page_token = None
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                while True:
                    params: dict[str, Any] = {"page_size": 200}
                    if page_token:
                        params["before"] = page_token
                    r = await c.get(f"{_BASE}/forms/{form_id}/responses",
                                    params=params, headers=self._headers())
                    r.raise_for_status()
                    data = r.json()
                    items = data.get("items", [])
                    results.extend(items)
                    if len(items) < 200:
                        break
                    page_token = items[-1]["token"]
        except Exception as exc:
            logger.error("export_responses: %s", exc)
        return results
