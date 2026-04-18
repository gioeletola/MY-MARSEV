"""Health alerter — sends Telegram or log alerts on consecutive health-check failures."""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_TELEGRAM_URL = "https://api.telegram.org/bot{token}/sendMessage"


class HealthAlerter:
    """Sends Telegram or log alerts when consecutive health checks fail.

    Parameters
    ----------
    telegram_token:
        Bot token (falls back to env ``TELEGRAM_BOT_TOKEN``).
    chat_id:
        Target chat ID (falls back to env ``TELEGRAM_ALERT_CHAT_ID``).
    threshold:
        Number of consecutive unhealthy checks before an alert fires.
    """

    def __init__(
        self,
        telegram_token: str = "",
        chat_id: str = "",
        threshold: int = 3,
    ) -> None:
        self._token: str = (
            telegram_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        )
        self._chat_id: str = (
            chat_id or os.environ.get("TELEGRAM_ALERT_CHAT_ID", "")
        )
        self._threshold = threshold
        self._consecutive_failures: int = 0
        self._alerts_sent: int = 0
        self._last_alert_ts: float | None = None
        self._http: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def check_and_alert(self, health: dict[str, Any]) -> None:
        """Process one health snapshot.

        If *health['overall']* is not ``'healthy'`` for >= *threshold*
        consecutive checks an alert is fired (Telegram if configured,
        otherwise a CRITICAL log line).
        """
        overall = health.get("overall", "unknown")
        if overall == "healthy":
            self._consecutive_failures = 0
            return

        self._consecutive_failures += 1
        logger.warning(
            "HealthAlerter: unhealthy check #%d (overall=%s)",
            self._consecutive_failures,
            overall,
        )

        if self._consecutive_failures >= self._threshold:
            await self._fire_alert(health)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _fire_alert(self, health: dict[str, Any]) -> None:
        msg = (
            f"ALERT: system unhealthy for {self._consecutive_failures} "
            f"consecutive checks.\nDetails: {health}"
        )
        logger.critical("HealthAlerter: %s", msg)
        self._alerts_sent += 1
        self._last_alert_ts = time.time()

        if self._token and self._chat_id:
            ok = await self._send_telegram(msg)
            if not ok:
                logger.error("HealthAlerter: Telegram send failed")

    async def _send_telegram(self, msg: str) -> bool:
        """POST message to Telegram Bot API.  Returns False on any error."""
        try:
            if self._http is None:
                self._http = httpx.AsyncClient(timeout=10.0)
            url = _TELEGRAM_URL.format(token=self._token)
            payload = {"chat_id": self._chat_id, "text": msg}
            resp = await self._http.post(url, json=payload)
            data: dict[str, Any] = resp.json()
            if not data.get("ok"):
                logger.warning("HealthAlerter Telegram error: %s", data)
                return False
            return True
        except Exception as exc:
            logger.error("HealthAlerter: _send_telegram exception: %s", exc)
            return False

    def get_stats(self) -> dict[str, Any]:
        """Return alerter statistics."""
        return {
            "alerts_sent": self._alerts_sent,
            "consecutive_failures": self._consecutive_failures,
            "last_alert_ts": self._last_alert_ts,
        }
