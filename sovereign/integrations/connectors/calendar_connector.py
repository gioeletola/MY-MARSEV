"""
Calendar connector — reads/writes events via CalDAV or Google Calendar REST API.
Supports iCal/CalDAV (read-write) and Google Calendar public API (read-only).
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sovereign.integrations.connectors.connector_base import (
    ConnectorBase,
    ConnectorHealth,
    ConnectorStatus,
    SyncResult,
)

logger = logging.getLogger(__name__)

_GCAL_BASE = "https://www.googleapis.com/calendar/v3"


class CalendarConnector(ConnectorBase):
    connector_id = "calendar"
    connector_name = "Calendar"
    connector_description = (
        "Reads/writes calendar events via CalDAV or Google Calendar API. "
        "Falls back to local ICS file for offline mode."
    )
    connector_status = ConnectorStatus.BETA
    requires_oauth = True
    required_scopes = ["https://www.googleapis.com/auth/calendar.readonly"]

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        # Google Calendar (OAuth access token or API key)
        self._access_token = (
            self._config.get("access_token")
            or os.getenv("GOOGLE_CALENDAR_ACCESS_TOKEN")
            or ""
        )
        self._gcal_api_key = (
            self._config.get("api_key")
            or os.getenv("GOOGLE_CALENDAR_API_KEY")
            or ""
        )
        self._calendar_id = self._config.get("calendar_id") or os.getenv("GOOGLE_CALENDAR_ID", "primary")

        # CalDAV
        self._caldav_url = self._config.get("caldav_url") or os.getenv("CALENDAR_CALDAV_URL", "")
        self._caldav_user = self._config.get("username") or os.getenv("CALENDAR_USERNAME", "")
        self._caldav_pass = self._config.get("password") or os.getenv("CALENDAR_PASSWORD", "")

        # ICS fallback
        self._ics_path = self._config.get("ics_path", "")

        self._days_ahead = self._config.get("days_ahead", 7)
        self._events: list[dict] = []

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    def _gcal_headers(self) -> dict[str, str]:
        if self._access_token:
            return {"Authorization": f"Bearer {self._access_token}"}
        return {}

    def _gcal_params(self, extra: dict | None = None) -> dict:
        params = extra or {}
        if self._gcal_api_key and not self._access_token:
            params["key"] = self._gcal_api_key
        return params

    def _caldav_auth(self) -> tuple[str, str] | None:
        if self._caldav_user and self._caldav_pass:
            return (self._caldav_user, self._caldav_pass)
        return None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        # ICS file takes highest priority
        if self._ics_path and os.path.exists(self._ics_path):
            self.connector_status = ConnectorStatus.CONNECTED
            self._logger.info("CalendarConnector: using local ICS file")
            return True

        # CalDAV
        if self._caldav_url and self._caldav_user:
            try:
                import httpx
                auth = self._caldav_auth()
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.request(
                        "PROPFIND",
                        self._caldav_url,
                        auth=auth,
                        headers={"Depth": "0", "Content-Type": "application/xml"},
                    )
                    if resp.status_code in (200, 207):
                        self._logger.info("CalendarConnector: connected via CalDAV")
                        self.connector_status = ConnectorStatus.CONNECTED
                        return True
                    self._logger.warning("CalendarConnector: CalDAV auth failed (%d)", resp.status_code)
            except Exception as exc:
                self._logger.error("CalendarConnector: CalDAV connect error: %s", exc)

        # Google Calendar
        if self._access_token or self._gcal_api_key:
            try:
                import httpx
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(
                        f"{_GCAL_BASE}/calendars/{self._calendar_id}",
                        headers=self._gcal_headers(),
                        params=self._gcal_params(),
                    )
                    if resp.status_code == 200:
                        cal_name = resp.json().get("summary", self._calendar_id)
                        self._logger.info("CalendarConnector: connected to Google Calendar '%s'", cal_name)
                        self.connector_status = ConnectorStatus.CONNECTED
                        return True
                    self._logger.warning("CalendarConnector: Google Calendar auth failed (%d)", resp.status_code)
            except Exception as exc:
                self._logger.error("CalendarConnector: Google Calendar connect error: %s", exc)

        self._logger.warning("CalendarConnector: no valid credentials configured")
        return False

    async def disconnect(self) -> None:
        self._events = []
        self.connector_status = ConnectorStatus.DISCONNECTED

    async def sync(self) -> SyncResult:
        if self._ics_path and os.path.exists(self._ics_path):
            return await self._sync_ics()
        if self._caldav_url and self._caldav_user:
            return await self._sync_caldav()
        if self._access_token or self._gcal_api_key:
            return await self._sync_gcal()
        return SyncResult(
            connector_id=self.connector_id,
            success=False,
            errors=["No access_token, CalDAV URL, or ICS path configured"],
        )

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_id=self.connector_id,
            status=self.connector_status,
            last_sync=self._last_sync,
            last_error=self._last_error,
            records_synced=len(self._events),
            metadata={
                "calendar_id": self._calendar_id,
                "days_ahead": self._days_ahead,
                "ics_fallback": bool(self._ics_path),
                "caldav_configured": bool(self._caldav_url and self._caldav_user),
                "gcal_configured": bool(self._access_token or self._gcal_api_key),
            },
        )

    # ------------------------------------------------------------------
    # Sync backends
    # ------------------------------------------------------------------

    async def _sync_gcal(self) -> SyncResult:
        try:
            import httpx
            self.connector_status = ConnectorStatus.SYNCING
            now = datetime.now(timezone.utc)
            time_min = now.isoformat()
            time_max = (now + timedelta(days=self._days_ahead)).isoformat()
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{_GCAL_BASE}/calendars/{self._calendar_id}/events",
                    headers=self._gcal_headers(),
                    params=self._gcal_params({
                        "timeMin": time_min,
                        "timeMax": time_max,
                        "singleEvents": "true",
                        "orderBy": "startTime",
                        "maxResults": "50",
                    }),
                )
                if resp.status_code == 200:
                    self._events = resp.json().get("items", [])
                    self.connector_status = ConnectorStatus.CONNECTED
                    result = SyncResult(
                        connector_id=self.connector_id,
                        success=True,
                        records_synced=len(self._events),
                    )
                    self._mark_sync(result)
                    return result
                return SyncResult(
                    connector_id=self.connector_id,
                    success=False,
                    errors=[f"HTTP {resp.status_code}: {resp.text[:200]}"],
                )
        except Exception as exc:
            self.connector_status = ConnectorStatus.ERROR
            return SyncResult(connector_id=self.connector_id, success=False, errors=[str(exc)])

    async def _sync_caldav(self) -> SyncResult:
        try:
            import httpx
            self.connector_status = ConnectorStatus.SYNCING
            now = datetime.now(timezone.utc)
            time_min = now.strftime("%Y%m%dT%H%M%SZ")
            time_max = (now + timedelta(days=self._days_ahead)).strftime("%Y%m%dT%H%M%SZ")
            report_xml = (
                '<?xml version="1.0" encoding="utf-8"?>'
                '<C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">'
                "<D:prop><D:getetag/><C:calendar-data/></D:prop>"
                "<C:filter><C:comp-filter name=\"VCALENDAR\">"
                f'<C:comp-filter name="VEVENT">'
                f'<C:time-range start="{time_min}" end="{time_max}"/>'
                "</C:comp-filter></C:comp-filter></C:filter>"
                "</C:calendar-query>"
            )
            auth = self._caldav_auth()
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.request(
                    "REPORT",
                    self._caldav_url,
                    auth=auth,
                    headers={"Depth": "1", "Content-Type": "application/xml"},
                    content=report_xml.encode(),
                )
                if resp.status_code in (200, 207):
                    events = self._parse_caldav_response(resp.text)
                    self._events = events
                    self.connector_status = ConnectorStatus.CONNECTED
                    result = SyncResult(
                        connector_id=self.connector_id,
                        success=True,
                        records_synced=len(events),
                    )
                    self._mark_sync(result)
                    return result
                return SyncResult(
                    connector_id=self.connector_id,
                    success=False,
                    errors=[f"CalDAV REPORT failed: HTTP {resp.status_code}"],
                )
        except Exception as exc:
            self.connector_status = ConnectorStatus.ERROR
            return SyncResult(connector_id=self.connector_id, success=False, errors=[str(exc)])

    async def _sync_ics(self) -> SyncResult:
        try:
            with open(self._ics_path) as f:
                content = f.read()
            events = self._parse_ics(content)
            self._events = events
            self.connector_status = ConnectorStatus.CONNECTED
            result = SyncResult(
                connector_id=self.connector_id,
                success=True,
                records_synced=len(events),
            )
            self._mark_sync(result)
            return result
        except Exception as exc:
            self.connector_status = ConnectorStatus.ERROR
            return SyncResult(connector_id=self.connector_id, success=False, errors=[str(exc)])

    # ------------------------------------------------------------------
    # Domain methods
    # ------------------------------------------------------------------

    async def get_upcoming_events(self, days: int = 7) -> list[dict]:
        """Return upcoming events within the next `days` days, syncing if needed."""
        old_days = self._days_ahead
        self._days_ahead = days
        await self.sync()
        self._days_ahead = old_days
        return self._events

    async def get_today_events(self) -> list[dict]:
        """Return events scheduled for today."""
        now = datetime.now(timezone.utc)
        today_str = now.strftime("%Y%m%d")
        all_events = await self.get_upcoming_events(days=1)
        today_events = []
        for evt in all_events:
            dtstart = evt.get("dtstart", "") or evt.get("start", {})
            if isinstance(dtstart, dict):
                dtstart = dtstart.get("dateTime", dtstart.get("date", ""))
            if today_str in str(dtstart).replace("-", ""):
                today_events.append(evt)
        return today_events

    async def create_event(
        self,
        title: str,
        start: str,
        end: str,
        description: str = "",
        location: str = "",
    ) -> dict:
        """
        Create a calendar event.
        For Google Calendar: uses the REST API (requires write scope / access token).
        For CalDAV: PUTs an iCal VEVENT block.
        Returns the created event dict or raises on error.
        """
        if self._caldav_url and self._caldav_user:
            return await self._create_caldav_event(title, start, end, description, location)
        if self._access_token:
            return await self._create_gcal_event(title, start, end, description, location)
        raise RuntimeError("CalendarConnector: no writable backend configured (need CalDAV or OAuth access token)")

    async def _create_gcal_event(
        self, title: str, start: str, end: str, description: str, location: str
    ) -> dict:
        import httpx
        body = {
            "summary": title,
            "description": description,
            "location": location,
            "start": {"dateTime": start, "timeZone": "UTC"},
            "end": {"dateTime": end, "timeZone": "UTC"},
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{_GCAL_BASE}/calendars/{self._calendar_id}/events",
                headers={**self._gcal_headers(), "Content-Type": "application/json"},
                json=body,
            )
            if resp.status_code in (200, 201):
                return resp.json()
            raise RuntimeError(f"CalendarConnector: create_event failed: HTTP {resp.status_code} {resp.text[:200]}")

    async def _create_caldav_event(
        self, title: str, start: str, end: str, description: str, location: str
    ) -> dict:
        import uuid
        import httpx
        uid = str(uuid.uuid4())
        # Normalise datetime strings to iCal format (remove dashes/colons/Z)
        dtstart = re.sub(r"[-:]", "", start).rstrip("Z") + "Z"
        dtend = re.sub(r"[-:]", "", end).rstrip("Z") + "Z"
        now_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        ics_content = (
            "BEGIN:VCALENDAR\r\n"
            "VERSION:2.0\r\n"
            "PRODID:-//SovereignAI//CalendarConnector//EN\r\n"
            "BEGIN:VEVENT\r\n"
            f"UID:{uid}\r\n"
            f"DTSTAMP:{now_str}\r\n"
            f"DTSTART:{dtstart}\r\n"
            f"DTEND:{dtend}\r\n"
            f"SUMMARY:{title}\r\n"
            f"DESCRIPTION:{description}\r\n"
            f"LOCATION:{location}\r\n"
            "END:VEVENT\r\n"
            "END:VCALENDAR\r\n"
        )
        event_url = self._caldav_url.rstrip("/") + f"/{uid}.ics"
        auth = self._caldav_auth()
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.put(
                event_url,
                auth=auth,
                headers={"Content-Type": "text/calendar; charset=utf-8"},
                content=ics_content.encode(),
            )
            if resp.status_code in (200, 201, 204):
                return {"uid": uid, "url": event_url, "summary": title, "dtstart": dtstart, "dtend": dtend}
            raise RuntimeError(f"CalendarConnector: CalDAV PUT failed: HTTP {resp.status_code}")

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _parse_ics(self, content: str) -> list[dict]:
        """Parse iCal content and return a list of VEVENT dicts."""
        events: list[dict] = []
        for block in re.split(r"BEGIN:VEVENT", content)[1:]:
            def _field(name: str, blk: str = block) -> str:
                m = re.search(rf"{name}[^:]*:(.*)", blk)
                return m.group(1).strip() if m else ""

            events.append({
                "summary": _field("SUMMARY"),
                "dtstart": _field("DTSTART"),
                "dtend": _field("DTEND"),
                "description": _field("DESCRIPTION"),
                "location": _field("LOCATION"),
                "uid": _field("UID"),
            })
        return events

    def _parse_caldav_response(self, xml_text: str) -> list[dict]:
        """Extract VEVENT data from a CalDAV REPORT XML response."""
        events: list[dict] = []
        for cal_data_match in re.finditer(r"<.*?calendar-data[^>]*>(.*?)</.*?calendar-data>", xml_text, re.DOTALL):
            ics_block = cal_data_match.group(1)
            parsed = self._parse_ics(ics_block)
            events.extend(parsed)
        return events

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def get_events(self) -> list[dict]:
        return self._events

    def upcoming_titles(self, n: int = 5) -> list[str]:
        return [e.get("summary", "") for e in self._events[:n] if e.get("summary")]
