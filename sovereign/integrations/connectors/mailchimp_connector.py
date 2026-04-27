"""Mailchimp connector — lists, campaigns, automations, analytics."""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

from .connector_base import ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult

logger = logging.getLogger("connector.mailchimp")


class MailchimpConnector(ConnectorBase):
    connector_id = "mailchimp"
    connector_name = "Mailchimp"
    connector_description = "Mailchimp — email lists, campaigns, automations, analytics."
    connector_status = ConnectorStatus.CONNECTED
    requires_oauth = False
    required_scopes: list[str] = []

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._api_key = os.environ.get("MAILCHIMP_API_KEY", "")
        dc = self._api_key.split("-")[-1] if "-" in self._api_key else "us1"
        self._base = f"https://{dc}.api.mailchimp.com/3.0"
        self._data: dict[str, Any] = {}
        self._error_count = 0

    def _auth(self) -> tuple[str, str]:
        return ("anystring", self._api_key)

    async def connect(self) -> bool:
        if not self._api_key:
            self._last_error = "MAILCHIMP_API_KEY required"
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{self._base}/ping", auth=self._auth())
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
            lists = await self.get_list_stats()
            self._data["lists"] = lists
            self._last_sync = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
            count = len(lists) if isinstance(lists, list) else 1
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

    async def get_list_stats(self) -> list[dict]:
        """Return all audience lists with stats."""
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{self._base}/lists", params={"count": 20, "fields": "lists.id,lists.name,lists.stats"},
                                auth=self._auth())
                r.raise_for_status()
                return r.json().get("lists", [])
        except Exception as exc:
            return [{"error": str(exc)}]

    async def send_campaign(self, campaign_id: str) -> dict[str, Any]:
        """Send an existing ready campaign."""
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(f"{self._base}/campaigns/{campaign_id}/actions/send", auth=self._auth())
                r.raise_for_status()
                return {"sent": True, "campaign_id": campaign_id}
        except Exception as exc:
            return {"sent": False, "error": str(exc)}

    async def get_campaign_report(self, campaign_id: str) -> dict[str, Any]:
        """Get performance report for a campaign."""
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{self._base}/reports/{campaign_id}", auth=self._auth())
                r.raise_for_status()
                return r.json()
        except Exception as exc:
            return {"error": str(exc)}
