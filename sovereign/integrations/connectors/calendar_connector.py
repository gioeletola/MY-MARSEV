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
    connector_status = ConnectorStatus.CONNECTED
    requires_oauth = True
    required_scopes = [
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/calendar.events",
    ]

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._access_token = (
            self._config.get("access_token")
            or os.getenv("GOOGLE_CALENDAR_ACCESS_TOKEN")
            or ""
        )
        self._refresh_token = (
            self._config.get("refresh_token")
            or os.getenv("GOOGLE_CALENDAR_REFRESH_TOKEN")
            or ""
        )
        self._gcal_api_key = (
            self._config.get("api_key")
            or os.getenv("GOOGLE_CALENDAR_API_KEY")
            or ""
        )
        self._calendar_id = self._config.get("calendar_id") or os.getenv("GOOGLE_CALENDAR_ID", "primary")

        self._caldav_url  = self._config.get("caldav_url")  or os.getenv("CALENDAR_CALDAV_URL", "")
        self._caldav_user = self._config.get("username")    or os.getenv("CALENDAR_USERNAME", "")
        self._caldav_pass = self._config.get("password")    or os.getenv("CALENDAR_PASSWORD", "")
        self._ics_path    = self._config.get("ics_path", "")
        self._days_ahead  = self._config.get("days_ahead", 7)
        self._events: list[dict] = []

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    async def _ensure_token(self) -> None:
        """Proactively refresh the Google Calendar access token if near expiry."""
        if not self._refresh_token:
            return
        try:
            from sovereign.integrations.connectors.oauth_refresh import ensure_fresh_token
            fresh = await ensure_fresh_token(self._access_token, self._refresh_token)
            if fresh and fresh != self._access_token:
                self._access_token = fresh
        except Exception as exc:
            logger.debug("CalendarConnector._ensure_token: %s", exc)

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
        if self._ics_path and os.path.exists(self._ics_path):
            self.connector_status = ConnectorStatus.CONNECTED
            self._logger.info("CalendarConnector: using local ICS file")
            return True

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

        if self._access_token or self._refresh_token or self._gcal_api_key:
            await self._ensure_token()
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
        if self._access_token or self._refresh_token or self._gcal_api_key:
            await self._ensure_token()
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
                "refresh_token_set": bool(self._refresh_token),
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
                '<C:filter><C:comp-filter name="VCALENDAR">'
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
        old_days = self._days_ahead
        self._days_ahead = days
        await self.sync()
        self._days_ahead = old_days
        return self._events

    async def get_today_events(self) -> list[dict]:
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
        attendees: list[str] | None = None,
        calendar_id: str | None = None,
    ) -> dict[str, Any]:
        await self._ensure_token()
        if not self._access_token and not (self._caldav_url and self._caldav_user):
            return {"error": "No access token — configure GOOGLE_CALENDAR_ACCESS_TOKEN"}
        if self._caldav_url and self._caldav_user:
            try:
                return await self._create_caldav_event(title, start, end, description, location)
            except Exception as exc:
                return {"error": str(exc)}
        return await self._create_gcal_event_ext(title, start, end, description, location, attendees, calendar_id)

    async def _create_gcal_event(self, title: str, start: str, end: str, description: str, location: str) -> dict:
        import httpx
        body = {
            "summary": title, "description": description, "location": location,
            "start": {"dateTime": start, "timeZone": "UTC"},
            "end":   {"dateTime": end,   "timeZone": "UTC"},
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

    async def _create_gcal_event_ext(
        self, title: str, start: str, end: str, description: str, location: str,
        attendees: list[str] | None, calendar_id: str | None,
    ) -> dict[str, Any]:
        if not self._access_token:
            return {"error": "No access token — configure GOOGLE_CALENDAR_ACCESS_TOKEN"}
        cal_id = calendar_id or self._calendar_id
        body: dict[str, Any] = {
            "summary": title, "description": description, "location": location,
            "start": {"dateTime": start}, "end": {"dateTime": end},
        }
        if attendees:
            body["attendees"] = [{"email": a} for a in attendees]
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{_GCAL_BASE}/calendars/{cal_id}/events",
                    headers={"Authorization": f"Bearer {self._access_token}", "Content-Type": "application/json"},
                    json=body,
                )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    return {"event_id": data.get("id", ""), "html_link": data.get("htmlLink", "")}
                return {"error": f"Calendar API {resp.status_code}: {resp.text[:200]}"}
        except Exception as exc:
            return {"error": str(exc)}

    async def update_event(
        self, event_id: str, title: str | None = None, start: str | None = None,
        end: str | None = None, description: str | None = None, calendar_id: str | None = None,
    ) -> dict[str, Any]:
        await self._ensure_token()
        if not self._access_token:
            return {"error": "No access token"}
        cal_id = calendar_id or self._calendar_id
        patch: dict[str, Any] = {}
        if title:       patch["summary"] = title
        if description is not None: patch["description"] = description
        if start:       patch["start"] = {"dateTime": start}
        if end:         patch["end"]   = {"dateTime": end}
        if not patch:
            return {"error": "No fields to update"}
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.patch(
                    f"{_GCAL_BASE}/calendars/{cal_id}/events/{event_id}",
                    headers={"Authorization": f"Bearer {self._access_token}", "Content-Type": "application/json"},
                    json=patch,
                )
                return {"updated": resp.status_code == 200, "status": resp.status_code}
        except Exception as exc:
            return {"error": str(exc)}

    async def delete_event(self, event_id: str, calendar_id: str | None = None) -> dict[str, Any]:
        await self._ensure_token()
        if not self._access_token:
            return {"error": "No access token"}
        cal_id = calendar_id or self._calendar_id
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.delete(
                    f"{_GCAL_BASE}/calendars/{cal_id}/events/{event_id}",
                    headers={"Authorization": f"Bearer {self._access_token}"},
                )
                return {"deleted": resp.status_code == 204, "status": resp.status_code}
        except Exception as exc:
            return {"error": str(exc)}

    async def _create_caldav_event(
        self, title: str, start: str, end: str, description: str, location: str
    ) -> dict:
        import uuid
        import httpx
        uid = str(uuid.uuid4())
        dtstart = re.sub(r"[-:]", "", start).rstrip("Z") + "Z"
        dtend   = re.sub(r"[-:]", "", end).rstrip("Z") + "Z"
        now_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        ics_content = (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//SovereignAI//CalendarConnector//EN\r\n"
            "BEGIN:VEVENT\r\n"
            f"UID:{uid}\r\nDTSTAMP:{now_str}\r\nDTSTART:{dtstart}\r\nDTEND:{dtend}\r\n"
            f"SUMMARY:{title}\r\nDESCRIPTION:{description}\r\nLOCATION:{location}\r\n"
            "END:VEVENT\r\nEND:VCALENDAR\r\n"
        )
        event_url = self._caldav_url.rstrip("/") + f"/{uid}.ics"
        auth = self._caldav_auth()
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.put(
                event_url, auth=auth,
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
        events: list[dict] = []
        for block in re.split(r"BEGIN:VEVENT", content)[1:]:
            def _field(name: str, blk: str = block) -> str:
                m = re.search(rf"{name}[^:]*(.*)", blk)
                return m.group(1).strip() if m else ""
            events.append({
                "summary": _field("SUMMARY"), "dtstart": _field("DTSTART"),
                "dtend": _field("DTEND"), "description": _field("DESCRIPTION"),
                "location": _field("LOCATION"), "uid": _field("UID"),
            })
        return events

    def _parse_caldav_response(self, xml_text: str) -> list[dict]:
        events: list[dict] = []
        for cal_data_match in re.finditer(r"<.*?calendar-data[^>]*>(.*?)</.*?calendar-data>", xml_text, re.DOTALL):
            ics_block = cal_data_match.group(1)
            events.extend(self._parse_ics(ics_block))
        return events

    def get_events(self) -> list[dict]:
        return self._events

    def upcoming_titles(self, n: int = 5) -> list[str]:
        return [e.get("summary", "") for e in self._events[:n] if e.get("summary")]
