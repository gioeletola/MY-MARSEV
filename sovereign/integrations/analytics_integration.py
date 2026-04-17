"""Analytics integration stub."""
from __future__ import annotations

import logging

from sovereign.integrations.base_integration import (
    BaseIntegration,
    IntegrationConfig,
    IntegrationStatus,
)

logger = logging.getLogger(__name__)


class AnalyticsIntegration(BaseIntegration):
    """Stub connector for analytics platforms (GA4, Plausible, Mixpanel, etc.)."""

    integration_id = "analytics"
    name = "Analytics Integration"

    # ------------------------------------------------------------------
    # BaseIntegration interface
    # ------------------------------------------------------------------

    def connect(self, config: IntegrationConfig) -> bool:
        """Connect stub."""
        logger.debug("analytics.connect: stub")
        self._status = IntegrationStatus.DISCONNECTED
        return False

    def disconnect(self) -> bool:
        """Disconnect stub."""
        logger.debug("analytics.disconnect: stub")
        self._status = IntegrationStatus.DISCONNECTED
        return False

    def test_connection(self) -> bool:
        """Connection probe stub."""
        logger.debug("analytics.test_connection: stub")
        return False

    def fetch(self, resource: str, params: dict) -> dict:
        """Generic fetch stub."""
        logger.debug("analytics.fetch: stub")
        return {}

    def push(self, resource: str, data: dict) -> dict:
        """Generic push stub."""
        logger.debug("analytics.push: stub")
        return {}

    # ------------------------------------------------------------------
    # Analytics-specific helpers
    # ------------------------------------------------------------------

    def get_pageviews(self, date_range: str) -> dict:
        """Return pageview metrics for *date_range* — not implemented."""
        logger.debug("analytics.get_pageviews: stub")
        return {}

    def get_events(self, event_name: str, date_range: str) -> list[dict]:
        """Return occurrences of *event_name* in *date_range* — not implemented."""
        logger.debug("analytics.get_events: stub")
        return []

    def get_conversions(self, date_range: str) -> dict:
        """Return conversion metrics for *date_range* — not implemented."""
        logger.debug("analytics.get_conversions: stub")
        return {}

    def get_top_pages(self, limit: int = 10) -> list[dict]:
        """Return the top *limit* pages by traffic — not implemented."""
        logger.debug("analytics.get_top_pages: stub")
        return []
