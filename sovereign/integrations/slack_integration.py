"""Slack integration — Incoming Webhooks + Web API (chat.postMessage)."""
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

_SLACK_POST_MESSAGE_URL = "https://slack.com/api/chat.postMessage"


class SlackIntegration(BaseIntegration):
    """Slack Incoming Webhooks + Web API (chat.postMessage)."""

    integration_id = "slack"
    name = "Slack Integration"

    def __init__(
        self,
        webhook_url: str = "",
        bot_token: str = "",
    ) -> None:
        super().__init__()
        self._webhook_url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL", "")
        self._bot_token = bot_token or os.environ.get("SLACK_BOT_TOKEN", "")

    # ------------------------------------------------------------------
    # BaseIntegration interface
    # ------------------------------------------------------------------

    def connect(self, config: IntegrationConfig) -> bool:
        creds = config.credentials or {}
        settings = config.settings or {}
        self._webhook_url = (
            creds.get("webhook_url")
            or settings.get("webhook_url")
            or self._webhook_url
        )
        self._bot_token = (
            creds.get("bot_token")
            or settings.get("bot_token")
            or self._bot_token
        )
        self._status = IntegrationStatus.CONNECTED
        logger.info(
            "SlackIntegration.connect: webhook=%s web_api=%s",
            bool(self._webhook_url),
            bool(self._bot_token),
        )
        return True

    def disconnect(self) -> bool:
        self._status = IntegrationStatus.DISCONNECTED
        return True

    def test_connection(self) -> bool:
        return bool(self._webhook_url or self._bot_token)

    def fetch(self, resource: str, params: dict) -> dict:
        """Slack write-only via webhooks; basic fetch stub."""
        return {}

    def push(self, resource: str, data: dict) -> dict:
        """
        Post a message to Slack.

        resource="message" — post via Incoming Webhook (preferred) or Web API.
        data keys: text, channel, username, icon_emoji
        """
        if resource != "message":
            logger.warning("SlackIntegration.push: unknown resource '%s'", resource)
            return {"ok": False, "error": f"unknown resource: {resource}"}

        if self._webhook_url:
            return self._post_webhook(data)
        if self._bot_token:
            return self._post_web_api(data)

        logger.warning("SlackIntegration.push: no webhook_url or bot_token configured")
        return {"ok": False, "error": "no Slack credentials configured"}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _post_webhook(self, data: dict) -> dict:
        payload: dict = {"text": data.get("text", "")}
        for key in ("channel", "username", "icon_emoji"):
            if key in data:
                payload[key] = data[key]
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(self._webhook_url, json=payload)
            ok = resp.is_success and resp.text == "ok"
            return {"status_code": resp.status_code, "ok": ok}
        except Exception as exc:
            logger.error("SlackIntegration._post_webhook error: %s", exc)
            return {"status_code": 0, "ok": False, "error": str(exc)}

    def _post_web_api(self, data: dict) -> dict:
        payload: dict = {
            "text": data.get("text", ""),
            "channel": data.get("channel", "#general"),
        }
        for key in ("username", "icon_emoji"):
            if key in data:
                payload[key] = data[key]
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    _SLACK_POST_MESSAGE_URL,
                    json=payload,
                    headers={"Authorization": f"Bearer {self._bot_token}"},
                )
            body = resp.json()
            return {"status_code": resp.status_code, "ok": body.get("ok", False)}
        except Exception as exc:
            logger.error("SlackIntegration._post_web_api error: %s", exc)
            return {"status_code": 0, "ok": False, "error": str(exc)}
