"""Generic outbound webhook integration — POSTs JSON payloads to a configured URL."""
from __future__ import annotations

import logging
import os

import httpx

from sovereign.integrations.base_integration import (
    BaseIntegration,
    IntegrationConfig,
    IntegrationStatus,
)

logger = logging.getLogger(__name__)


class WebhookIntegration(BaseIntegration):
    """Generic outbound webhook — POSTs JSON payloads to a configured URL."""

    integration_id = "webhook"
    name = "Webhook Integration"

    def __init__(self, webhook_url: str = "") -> None:
        super().__init__()
        self._webhook_url = webhook_url or os.environ.get("WEBHOOK_URL", "")

    # ------------------------------------------------------------------
    # BaseIntegration interface
    # ------------------------------------------------------------------

    def connect(self, config: IntegrationConfig) -> bool:
        url = config.settings.get("webhook_url", "") or config.credentials.get(
            "webhook_url", ""
        )
        if url:
            self._webhook_url = url
        self._status = IntegrationStatus.CONNECTED
        logger.info("WebhookIntegration.connect: url=%s", self._webhook_url or "(env)")
        return True

    def disconnect(self) -> bool:
        self._status = IntegrationStatus.DISCONNECTED
        return True

    def test_connection(self) -> bool:
        return bool(self._webhook_url)

    def fetch(self, resource: str, params: dict) -> dict:
        """Webhooks are outbound-only — fetch returns empty."""
        return {}

    def push(self, resource: str, data: dict) -> dict:
        """POST *data* as JSON to the configured webhook URL."""
        if not self._webhook_url:
            logger.warning("WebhookIntegration.push: no webhook_url configured")
            return {"status_code": 0, "ok": False, "error": "no webhook_url configured"}
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(self._webhook_url, json=data)
            return {"status_code": resp.status_code, "ok": resp.is_success}
        except Exception as exc:
            logger.error("WebhookIntegration.push error: %s", exc)
            return {"status_code": 0, "ok": False, "error": str(exc)}
