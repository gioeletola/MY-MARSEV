"""Telegram integration stub.

Requires TELEGRAM_BOT_TOKEN in secrets.
"""
from __future__ import annotations

import logging

from sovereign.integrations.base_integration import (
    BaseIntegration,
    IntegrationConfig,
    IntegrationStatus,
)

logger = logging.getLogger(__name__)


class TelegramIntegration(BaseIntegration):
    """Stub connector for the Telegram Bot API.

    Requires TELEGRAM_BOT_TOKEN in secrets.
    """

    integration_id = "telegram"
    name = "Telegram Integration"

    # ------------------------------------------------------------------
    # BaseIntegration interface
    # ------------------------------------------------------------------

    def connect(self, config: IntegrationConfig) -> bool:
        """Connect stub."""
        logger.debug("telegram.connect: stub")
        self._status = IntegrationStatus.DISCONNECTED
        return False

    def disconnect(self) -> bool:
        """Disconnect stub."""
        logger.debug("telegram.disconnect: stub")
        self._status = IntegrationStatus.DISCONNECTED
        return False

    def test_connection(self) -> bool:
        """Connection probe stub."""
        logger.debug("telegram.test_connection: stub")
        return False

    def fetch(self, resource: str, params: dict) -> dict:
        """Generic fetch stub."""
        logger.debug("telegram.fetch: stub")
        return {}

    def push(self, resource: str, data: dict) -> dict:
        """Generic push stub."""
        logger.debug("telegram.push: stub")
        return {}

    # ------------------------------------------------------------------
    # Telegram-specific helpers
    # ------------------------------------------------------------------

    def send_message(self, chat_id: str, text: str) -> bool:
        """Send a text message to *chat_id* — not implemented."""
        logger.debug("telegram.send_message: stub")
        return False

    def send_file(self, chat_id: str, file_path: str) -> bool:
        """Upload a file at *file_path* to *chat_id* — not implemented."""
        logger.debug("telegram.send_file: stub")
        return False

    def get_updates(self) -> list[dict]:
        """Poll for incoming bot updates — not implemented."""
        logger.debug("telegram.get_updates: stub")
        return []
