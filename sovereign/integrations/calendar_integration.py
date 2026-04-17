"""
Calendar integration — local JSON event store with optional CalDAV/HTTP backend.

Out-of-the-box behaviour (no credentials):
  - Events are stored in data/memory/calendar.json
  - Full CRUD for events: create, update, delete, query by date range

With credentials (IntegrationConfig.credentials):
  - caldav_url, caldav_user, caldav_password → real CalDAV HTTP sync (stub, extend as needed)
"""
from __future__ import annotations

import json
import logging
import pathlib
import uuid
from datetime import datetime, timezone, date
from typing import Any

from sovereign.integrations.base_integration import (
    BaseIntegration,
    IntegrationConfig,
    IntegrationStatus,
)

logger = logging.getLogger(__name__)

_CALENDAR_FILE = pathlib.Path("data/memory/calendar.json")


def _load_events() -> list[dict]:
    if not _CALENDAR_FILE.exists():
        return []
    try:
        return json.loads(_CALENDAR_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_events(events: list[dict]) -> None:
    _CALENDAR_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CALENDAR_FILE.write_text(json.dumps(events, indent=2, ensure_ascii=False), encoding="utf-8")


class CalendarIntegration(BaseIntegration):
    """
    Calendar connector with local-first storage.

    Local format (data/memory/calendar.json) — list of event dicts:
      id, title, start (ISO), end (ISO), description, location, all_day, created_at
    """

    integration_id = "calendar"
    name = "Calendar Integration"

    def __init__(self) -> None:
        super().__init__()
        self._caldav_cfg: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # BaseIntegration interface
    # ------------------------------------------------------------------

    def connect(self, config: IntegrationConfig) -> bool:
        creds = config.credentials or {}
        self._caldav_cfg = {k: v for k, v in creds.items() if k.startswith("caldav_")}
        self._status = IntegrationStatus.CONNECTED
        logger.info("calendar.connect: caldav=%s", bool(self._caldav_cfg.get("caldav_url")))
        return True

    def disconnect(self) -> bool:
        self._caldav_cfg = {}
        self._status = IntegrationStatus.DISCONNECTED
        return True

    def test_connection(self) -> bool:
        if self._caldav_cfg.get("caldav_url"):
            try:
                import urllib.request
                urllib.request.urlopen(self._caldav_cfg["caldav_url"], timeout=5)
                return True
            except Exception:
                return False
        return True  # local store always available

    def fetch(self, resource: str, params: dict) -> dict:
        if resource == "events":
            return {"events": self.get_events(
                params.get("date_from", ""),
                params.get("date_to", ""),
            )}
        if resource == "today":
            return {"events": self.get_today()}
        return {}

    def push(self, resource: str, data: dict) -> dict:
        if resource == "event":
            return self.create_event(
                data.get("title", ""),
                data.get("start", ""),
                data.get("end", ""),
                data.get("description", ""),
            )
        return {}

    # ------------------------------------------------------------------
    # Calendar-specific API
    # ------------------------------------------------------------------

    def get_events(self, date_from: str, date_to: str) -> list[dict]:
        """Return events whose start falls in [date_from, date_to] (ISO date strings)."""
        events = _load_events()
        if not date_from and not date_to:
            return events
        result = []
        for ev in events:
            start = ev.get("start", "")[:10]  # YYYY-MM-DD
            if date_from and start < date_from:
                continue
            if date_to and start > date_to:
                continue
            result.append(ev)
        return result

    def create_event(
        self,
        title: str,
        start: str,
        end: str,
        description: str = "",
        location: str = "",
        all_day: bool = False,
    ) -> dict:
        """Create a new calendar event and persist it."""
        event = {
            "id":          str(uuid.uuid4())[:8],
            "title":       title,
            "start":       start,
            "end":         end,
            "description": description,
            "location":    location,
            "all_day":     all_day,
            "created_at":  datetime.now(timezone.utc).isoformat(),
        }
        events = _load_events()
        events.append(event)
        _save_events(events)
        logger.info("calendar.create_event: '%s' at %s", title, start)
        return event

    def update_event(self, event_id: str, updates: dict) -> bool:
        """Apply *updates* to the event identified by *event_id*."""
        events = _load_events()
        for ev in events:
            if ev.get("id") == event_id:
                ev.update({k: v for k, v in updates.items() if k != "id"})
                ev["updated_at"] = datetime.now(timezone.utc).isoformat()
                _save_events(events)
                return True
        return False

    def delete_event(self, event_id: str) -> bool:
        """Delete the event identified by *event_id*."""
        events = _load_events()
        new_events = [ev for ev in events if ev.get("id") != event_id]
        if len(new_events) == len(events):
            return False
        _save_events(new_events)
        return True

    def get_today(self) -> list[dict]:
        """Return all events scheduled for today (UTC date)."""
        today = date.today().isoformat()
        return self.get_events(today, today)

    def get_upcoming(self, days: int = 7) -> list[dict]:
        """Return events in the next *days* days."""
        from datetime import timedelta
        today = date.today()
        end = (today + timedelta(days=days)).isoformat()
        return self.get_events(today.isoformat(), end)

    def get_event(self, event_id: str) -> dict | None:
        """Return a single event by ID."""
        for ev in _load_events():
            if ev.get("id") == event_id:
                return ev
        return None
