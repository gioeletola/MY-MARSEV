"""Email integration stub.

Wire SMTP/IMAP credentials via SecretManager before activating this connector.
"""
from __future__ import annotations

import logging

from sovereign.integrations.base_integration import (
    BaseIntegration,
    IntegrationConfig,
    IntegrationStatus,
)

logger = logging.getLogger(__name__)


class EmailIntegration(BaseIntegration):
    """Stub connector for SMTP/IMAP email services.

    Wire SMTP/IMAP credentials via SecretManager.
    """

    integration_id = "email"
    name = "Email Integration"

    # ------------------------------------------------------------------
    # BaseIntegration interface
    # ------------------------------------------------------------------

    def connect(self, config: IntegrationConfig) -> bool:
        """Connect stub — no-op until credentials are wired."""
        logger.debug("email.connect: stub")
        self._status = IntegrationStatus.DISCONNECTED
        return False

    def disconnect(self) -> bool:
        """Disconnect stub."""
        logger.debug("email.disconnect: stub")
        self._status = IntegrationStatus.DISCONNECTED
        return False

    def test_connection(self) -> bool:
        """Connection probe stub."""
        logger.debug("email.test_connection: stub")
        return False

    def fetch(self, resource: str, params: dict) -> dict:
        """Generic fetch stub."""
        logger.debug("email.fetch: stub")
        return {}

    def push(self, resource: str, data: dict) -> dict:
        """Generic push stub."""
        logger.debug("email.push: stub")
        return {}

    # ------------------------------------------------------------------
    # Email-specific helpers
    # ------------------------------------------------------------------

    def send_email(self, to: str, subject: str, body: str) -> bool:
        """Send an email — not implemented."""
        logger.debug("email.send_email: stub")
        return False

    def fetch_inbox(self, limit: int = 20) -> list[dict]:
        """Return the most recent *limit* messages — not implemented."""
        logger.debug("email.fetch_inbox: stub")
        return []

    def search_emails(self, query: str) -> list[dict]:
        """Search messages matching *query* — not implemented."""
        logger.debug("email.search_emails: stub")
        return []

    def mark_read(self, message_id: str) -> bool:
        """Mark message *message_id* as read — not implemented."""
        logger.debug("email.mark_read: stub")
        return False
