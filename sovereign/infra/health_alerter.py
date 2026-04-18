<<<<<<< HEAD
"""Health alerter — sends Telegram or log alerts on consecutive health-check failures."""
=======
"""Health alerter — sends Telegram or log alerts when health checks fail."""
>>>>>>> b0c71f2 (feat(multi-provider+h24): OpenAI/Gemini providers, H24 worker pool, watchdog, health alerter, live integrations)
from __future__ import annotations

import logging
import os
<<<<<<< HEAD
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
=======
from typing import Any

logger = logging.getLogger(__name__)


class HealthAlerter:
    """Sends Telegram / log alerts when health check fails N consecutive times."""
>>>>>>> b0c71f2 (feat(multi-provider+h24): OpenAI/Gemini providers, H24 worker pool, watchdog, health alerter, live integrations)

    def __init__(
        self,
        telegram_token: str = "",
        chat_id: str = "",
<<<<<<< HEAD
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
=======
        threshold_failures: int = 3,
    ) -> None:
        self._token = telegram_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self._chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self._threshold = threshold_failures
        self._consecutive_failures = 0
        self._total_checks = 0
        self._total_alerts_sent = 0

    async def check_and_alert(self, health: dict[str, Any]) -> None:
        """
        Called by the health monitor after each check.

        Sends an alert if overall != 'healthy' for *threshold_failures*
        consecutive checks.
        """
        self._total_checks += 1
        overall = health.get("overall", "unknown")

        if overall != "healthy":
            self._consecutive_failures += 1
            logger.warning(
                "HealthAlerter: unhealthy check #%d (%s)",
                self._consecutive_failures,
                overall,
            )
            if self._consecutive_failures >= self._threshold:
                msg = (
                    f"SOVEREIGN HEALTH ALERT\n"
                    f"Status: {overall}\n"
                    f"Consecutive failures: {self._consecutive_failures}\n"
                    f"Details: {health}"
                )
                sent = await self._send_telegram(msg)
                if sent:
                    self._total_alerts_sent += 1
                else:
                    logger.error("HealthAlerter: alert for '%s' could not be sent", overall)
        else:
            if self._consecutive_failures > 0:
                logger.info(
                    "HealthAlerter: system recovered after %d failures",
                    self._consecutive_failures,
                )
            self._consecutive_failures = 0

    async def _send_telegram(self, msg: str) -> bool:
        """POST to Telegram Bot API — graceful on failure."""
        if not self._token or not self._chat_id:
            logger.warning(
                "HealthAlerter: Telegram not configured (token/chat_id missing) — "
                "logging alert instead: %s",
                msg,
            )
            return False
        try:
            import httpx

            url = f"https://api.telegram.org/bot{self._token}/sendMessage"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    url,
                    json={"chat_id": self._chat_id, "text": msg},
                )
            if resp.status_code == 200:
                logger.debug("HealthAlerter: Telegram alert sent")
                return True
            logger.warning(
                "HealthAlerter: Telegram API returned %d", resp.status_code
            )
            return False
        except Exception as exc:
            logger.warning("HealthAlerter: Telegram send failed: %s", exc)
            return False

    def get_stats(self) -> dict[str, int]:
        return {
            "total_checks": self._total_checks,
            "consecutive_failures": self._consecutive_failures,
            "total_alerts_sent": self._total_alerts_sent,
            "threshold": self._threshold,
>>>>>>> b0c71f2 (feat(multi-provider+h24): OpenAI/Gemini providers, H24 worker pool, watchdog, health alerter, live integrations)
        }
