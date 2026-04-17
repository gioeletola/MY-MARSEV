"""CRM integration stub."""
from __future__ import annotations

import logging

from sovereign.integrations.base_integration import (
    BaseIntegration,
    IntegrationConfig,
    IntegrationStatus,
)

logger = logging.getLogger(__name__)


class CRMIntegration(BaseIntegration):
    """Stub connector for CRM platforms (HubSpot, Salesforce, etc.)."""

    integration_id = "crm"
    name = "CRM Integration"

    # ------------------------------------------------------------------
    # BaseIntegration interface
    # ------------------------------------------------------------------

    def connect(self, config: IntegrationConfig) -> bool:
        """Connect stub."""
        logger.debug("crm.connect: stub")
        self._status = IntegrationStatus.DISCONNECTED
        return False

    def disconnect(self) -> bool:
        """Disconnect stub."""
        logger.debug("crm.disconnect: stub")
        self._status = IntegrationStatus.DISCONNECTED
        return False

    def test_connection(self) -> bool:
        """Connection probe stub."""
        logger.debug("crm.test_connection: stub")
        return False

    def fetch(self, resource: str, params: dict) -> dict:
        """Generic fetch stub."""
        logger.debug("crm.fetch: stub")
        return {}

    def push(self, resource: str, data: dict) -> dict:
        """Generic push stub."""
        logger.debug("crm.push: stub")
        return {}

    # ------------------------------------------------------------------
    # CRM-specific helpers
    # ------------------------------------------------------------------

    def get_contacts(self, limit: int = 50) -> list[dict]:
        """Return up to *limit* contacts — not implemented."""
        logger.debug("crm.get_contacts: stub")
        return []

    def create_contact(self, data: dict) -> dict:
        """Create a new contact record — not implemented."""
        logger.debug("crm.create_contact: stub")
        return {}

    def update_contact(self, contact_id: str, data: dict) -> bool:
        """Apply *data* updates to contact *contact_id* — not implemented."""
        logger.debug("crm.update_contact: stub")
        return False

    def get_pipeline(self) -> list[dict]:
        """Return all pipeline stages — not implemented."""
        logger.debug("crm.get_pipeline: stub")
        return []

    def create_deal(self, data: dict) -> dict:
        """Create a new deal — not implemented."""
        logger.debug("crm.create_deal: stub")
        return {}

    def log_activity(self, contact_id: str, activity: dict) -> bool:
        """Log an activity against contact *contact_id* — not implemented."""
        logger.debug("crm.log_activity: stub")
        return False
