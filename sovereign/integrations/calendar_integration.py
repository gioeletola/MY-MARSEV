"""Calendar integration stub."""
from __future__ import annotations

import logging

from sovereign.integrations.base_integration import (
    BaseIntegration,
    IntegrationConfig,
    IntegrationStatus,
)

logger = logging.getLogger(__name__)


class CalendarIntegration(BaseIntegration):
    """Stub connector for calendar services (Google Calendar, CalDAV, etc.)."""

    integration_id = "calendar"
    name = "Calendar Integration"

    # ------------------------------------------------------------------
    # BaseIntegration interface
    # ------------------------------------------------------------------

    def connect(self, config: IntegrationConfig) -> bool:
        """Connect stub."""
        logger.debug("calendar.connect: stub")
        self._status = IntegrationStatus.DISCONNECTED
        return False

    def disconnect(self) -> bool:
        """Disconnect stub."""
        logger.debug("calendar.disconnect: stub")
        self._status = IntegrationStatus.DISCONNECTED
        return False

    def test_connection(self) -> bool:
        """Connection probe stub."""
        logger.debug("calendar.test_connection: stub")
        return False

    def fetch(self, resource: str, params: dict) -> dict:
        """Generic fetch stub."""
        logger.debug("calendar.fetch: stub")
        return {}

    def push(self, resource: str, data: dict) -> dict:
        """Generic push stub."""
        logger.debug("calendar.push: stub")
        return {}

    # ------------------------------------------------------------------
    # Calendar-specific helpers
    # ------------------------------------------------------------------

    def get_events(self, date_from: str, date_to: str) -> list[dict]:
        """Return events between *date_from* and *date_to* — not implemented."""
        logger.debug("calendar.get_events: stub")
        return []

    def create_event(
        self,
        title: str,
        start: str,
        end: str,
        description: str = "",
    ) -> dict:
        """Create a calendar event — not implemented."""
        logger.debug("calendar.create_event: stub")
        return {}

    def update_event(self, event_id: str, updates: dict) -> bool:
        """Apply *updates* to event *event_id* — not implemented."""
        logger.debug("calendar.update_event: stub")
        return False

    def delete_event(self, event_id: str) -> bool:
        """Delete event *event_id* — not implemented."""
        logger.debug("calendar.delete_event: stub")
        return False

    def get_today(self) -> list[dict]:
        """Return today's events — not implemented."""
        logger.debug("calendar.get_today: stub")
        return []
