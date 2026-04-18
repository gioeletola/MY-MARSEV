<<<<<<< HEAD
"""Slack integration — webhook-based message push and Bot API support."""
=======
"""Slack integration — Incoming Webhooks + Web API (chat.postMessage)."""
>>>>>>> b0c71f2 (feat(multi-provider+h24): OpenAI/Gemini providers, H24 worker pool, watchdog, health alerter, live integrations)
from __future__ import annotations

import logging
import os
<<<<<<< HEAD
from typing import Any
=======
>>>>>>> b0c71f2 (feat(multi-provider+h24): OpenAI/Gemini providers, H24 worker pool, watchdog, health alerter, live integrations)

import httpx

from sovereign.integrations.base_integration import (
    BaseIntegration,
    IntegrationConfig,
    IntegrationStatus,
)

logger = logging.getLogger(__name__)

<<<<<<< HEAD
_SLACK_API_URL = "https://slack.com/api/chat.postMessage"


class SlackIntegration(BaseIntegration):
    """Slack connector.

    Credentials (via ``IntegrationConfig.credentials``):
        webhook_url      — Incoming Webhook URL (preferred for simple sends)
        bot_token        — Bot OAuth token (used when webhook_url absent)
        default_channel  — Default channel for messages

    Push ``resource='message'`` with ``data={text, channel, username}``.
    """
=======
_SLACK_POST_MESSAGE_URL = "https://slack.com/api/chat.postMessage"


class SlackIntegration(BaseIntegration):
    """Slack Incoming Webhooks + Web API (chat.postMessage)."""
>>>>>>> b0c71f2 (feat(multi-provider+h24): OpenAI/Gemini providers, H24 worker pool, watchdog, health alerter, live integrations)

    integration_id = "slack"
    name = "Slack Integration"

<<<<<<< HEAD
    def __init__(self) -> None:
        super().__init__()
        self._webhook_url: str = ""
        self._bot_token: str = ""
        self._default_channel: str = ""
        self._http: httpx.AsyncClient | None = None
=======
    def __init__(
        self,
        webhook_url: str = "",
        bot_token: str = "",
    ) -> None:
        super().__init__()
        self._webhook_url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL", "")
        self._bot_token = bot_token or os.environ.get("SLACK_BOT_TOKEN", "")
>>>>>>> b0c71f2 (feat(multi-provider+h24): OpenAI/Gemini providers, H24 worker pool, watchdog, health alerter, live integrations)

    # ------------------------------------------------------------------
    # BaseIntegration interface
    # ------------------------------------------------------------------

    def connect(self, config: IntegrationConfig) -> bool:
<<<<<<< HEAD
        """Store credentials and mark connected."""
        creds = config.credentials
        self._webhook_url = (
            creds.get("webhook_url")
            or os.environ.get("SLACK_WEBHOOK_URL", "")
        )
        self._bot_token = (
            creds.get("bot_token")
            or os.environ.get("SLACK_BOT_TOKEN", "")
        )
        self._default_channel = (
            creds.get("default_channel")
            or os.environ.get("SLACK_DEFAULT_CHANNEL", "#general")
        )

        if not self._webhook_url and not self._bot_token:
            logger.warning("SlackIntegration: no webhook_url or bot_token — disabled")
            self._status = IntegrationStatus.DISCONNECTED
            return False

        self._http = httpx.AsyncClient(timeout=15.0)
        self._status = IntegrationStatus.CONNECTED
        logger.info("SlackIntegration connected")
=======
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
>>>>>>> b0c71f2 (feat(multi-provider+h24): OpenAI/Gemini providers, H24 worker pool, watchdog, health alerter, live integrations)
        return True

    def disconnect(self) -> bool:
        self._status = IntegrationStatus.DISCONNECTED
        return True

    def test_connection(self) -> bool:
        return bool(self._webhook_url or self._bot_token)

<<<<<<< HEAD
    def fetch(self, resource: str, params: dict[str, Any]) -> dict[str, Any]:  # noqa: ARG002
        """Slack fetch not yet implemented — returns empty dict."""
        return {}

    def push(self, resource: str, data: dict[str, Any]) -> dict[str, Any]:
        """Push a message to Slack.

        Parameters
        ----------
        resource:
            Must be ``'message'``.
        data:
            ``text`` (required), ``channel`` (optional), ``username`` (optional).
        """
        if resource != "message":
            return {"ok": False, "error": f"unknown resource: {resource}"}

        import asyncio as _asyncio

        try:
            loop = _asyncio.new_event_loop()
            result = loop.run_until_complete(self._send_message(data))
            loop.close()
            return result
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Async helpers
    # ------------------------------------------------------------------

    async def _send_message(self, data: dict[str, Any]) -> dict[str, Any]:
        text = data.get("text", "")
        channel = data.get("channel") or self._default_channel
        username = data.get("username", "SovereignAI")

        if self._http is None:
            self._http = httpx.AsyncClient(timeout=15.0)

        if self._webhook_url:
            return await self._post_webhook({"text": text, "username": username})

        # Fall back to Bot API
        return await self._post_api(
            {"channel": channel, "text": text, "username": username}
        )

    async def _post_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = await self._http.post(  # type: ignore[union-attr]
                self._webhook_url, json=payload
            )
            if resp.status_code == 200 and resp.text == "ok":
                return {"ok": True}
            return {"ok": False, "error": resp.text}
        except Exception as exc:
            logger.error("SlackIntegration webhook error: %s", exc)
            return {"ok": False, "error": str(exc)}

    async def _post_api(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            headers = {
                "Authorization": f"Bearer {self._bot_token}",
                "Content-Type": "application/json",
            }
            resp = await self._http.post(  # type: ignore[union-attr]
                _SLACK_API_URL, json=payload, headers=headers
            )
            data: dict[str, Any] = resp.json()
            return data
        except Exception as exc:
            logger.error("SlackIntegration API error: %s", exc)
            return {"ok": False, "error": str(exc)}
=======
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
>>>>>>> b0c71f2 (feat(multi-provider+h24): OpenAI/Gemini providers, H24 worker pool, watchdog, health alerter, live integrations)
