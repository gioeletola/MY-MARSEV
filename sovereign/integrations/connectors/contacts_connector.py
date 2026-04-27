"""
Contacts connector — Google People API for contacts, groups, and birthday reminders.
Auth: OAuth2 (GOOGLE_CONTACTS_ACCESS_TOKEN).
Status: BETA — requires Google OAuth2 consent and People API scope.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from sovereign.integrations.connectors.connector_base import (
    ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult,
)

logger = logging.getLogger(__name__)
_API_BASE = "https://people.googleapis.com/v1"


class ContactsConnector(ConnectorBase):
    connector_id = "contacts"
    connector_name = "Google Contacts"
    connector_description = (
        "Syncs Google Contacts via People API. Supports contacts, groups, "
        "birthday reminders, and local contact mirroring."
    )
    connector_status = ConnectorStatus.BETA
    requires_oauth = True
    required_env_vars = ["GOOGLE_CONTACTS_ACCESS_TOKEN"]

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._access_token = self._config.get("access_token") or os.getenv("GOOGLE_CONTACTS_ACCESS_TOKEN", "")
        self.api_base = _API_BASE
        self._data: dict[str, Any] = {}
        self._error_count = 0

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
        }

    async def connect(self) -> bool:
        if not self._access_token:
            self._logger.warning("ContactsConnector: no access token configured")
            return False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.api_base}/people/me",
                    headers=self._headers(),
                    params={"personFields": "names,emailAddresses"},
                )
                if resp.status_code == 200:
                    self._data["me"] = resp.json()
                    self._logger.info("ContactsConnector: connected")
                    return True
                self._logger.warning("Contacts connect returned %d", resp.status_code)
                return False
        except Exception as exc:
            self._logger.error("ContactsConnector connect error: %s", exc)
            self._error_count += 1
            return False

    async def disconnect(self) -> None:
        self._data.clear()

    async def sync(self) -> SyncResult:
        records = 0
        errors: list[str] = []
        try:
            import httpx
            async with httpx.AsyncClient(timeout=20.0) as client:
                # All contacts
                r = await client.get(
                    f"{self.api_base}/people/me/connections",
                    headers=self._headers(),
                    params={
                        "personFields": "names,emailAddresses,phoneNumbers,birthdays,organizations",
                        "pageSize": 200,
                    },
                )
                if r.status_code == 200:
                    connections = r.json().get("connections", [])
                    self._data["contacts"] = connections
                    records += len(connections)
                else:
                    errors.append(f"contacts: {r.status_code}")

                # Contact groups
                r2 = await client.get(
                    f"{self.api_base}/contactGroups",
                    headers=self._headers(),
                )
                if r2.status_code == 200:
                    groups = r2.json().get("contactGroups", [])
                    self._data["groups"] = groups
                    records += len(groups)
                else:
                    errors.append(f"groups: {r2.status_code}")

        except Exception as exc:
            errors.append(str(exc))
            self._error_count += 1

        result = SyncResult(self.connector_id, not errors, records, errors)
        self._mark_sync(result)
        return result

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_id=self.connector_id,
            status=ConnectorStatus.BETA if self._access_token else ConnectorStatus.DISCONNECTED,
            last_sync=self._last_sync,
            last_error=self._last_error,
            records_synced=self._records_synced,
            latency_ms=0.0,
            metadata={"contact_count": len(self._data.get("contacts", [])), "error_count": self._error_count},
        )

    async def search_contact(self, query: str) -> list[dict]:
        """Search contacts by name or email using the People API search endpoint."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.api_base}/people:searchContacts",
                    headers=self._headers(),
                    params={"query": query, "readMask": "names,emailAddresses,phoneNumbers"},
                )
                if resp.status_code == 200:
                    return resp.json().get("results", [])
                return []
        except Exception as exc:
            self._logger.error("search_contact error: %s", exc)
            return []

    def get_upcoming_birthdays(self, days_ahead: int = 30) -> list[dict]:
        """Return contacts with birthdays in the next N days."""
        now = datetime.now(timezone.utc)
        upcoming = []
        for contact in self._data.get("contacts", []):
            for bday in contact.get("birthdays", []):
                date_info = bday.get("date", {})
                month = date_info.get("month")
                day = date_info.get("day")
                if not month or not day:
                    continue
                try:
                    bday_this_year = datetime(now.year, month, day, tzinfo=timezone.utc)
                    if bday_this_year < now:
                        bday_this_year = datetime(now.year + 1, month, day, tzinfo=timezone.utc)
                    delta = (bday_this_year - now).days
                    if 0 <= delta <= days_ahead:
                        name = contact.get("names", [{}])[0].get("displayName", "Unknown")
                        upcoming.append({
                            "name": name,
                            "birthday": f"{month:02d}-{day:02d}",
                            "days_until": delta,
                        })
                except ValueError:
                    continue
        return sorted(upcoming, key=lambda x: x["days_until"])

    def sync_to_local(self) -> list[dict]:
        """
        Return a simplified flat list of contacts suitable for local storage or export.
        """
        local_contacts = []
        for c in self._data.get("contacts", []):
            name = c.get("names", [{}])[0].get("displayName", "") if c.get("names") else ""
            emails = [e.get("value") for e in c.get("emailAddresses", [])]
            phones = [p.get("value") for p in c.get("phoneNumbers", [])]
            local_contacts.append({"name": name, "emails": emails, "phones": phones})
        return local_contacts

    def get_groups(self) -> list[dict]:
        """Return cached contact groups."""
        return self._data.get("groups", [])
