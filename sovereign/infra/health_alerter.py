"""Health alerter — sends Telegram or log alerts when health checks fail."""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


class HealthAlerter:
    """Sends Telegram / log alerts when health check fails N consecutive times."""

    def __init__(
        self,
        telegram_token: str = "",
        chat_id: str = "",
        threshold_failures: int = 3,
    ) -> None:
        self._token = telegram_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self._chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self._threshold = threshold_failures
        self._consecutive_failures = 0
        self._total_checks = 0
        self._total_alerts_sent = 0
        self._last_check_at: float = 0.0

    async def run_loop(
        self,
        check_fn: Callable[[], Awaitable[dict[str, Any]] | dict[str, Any]],
        interval_s: float = 30.0,
    ) -> None:
        """Run *check_fn* every *interval_s* seconds and pass the result to
        :meth:`check_and_alert`.  Runs until cancelled."""
        while True:
            try:
                result = check_fn()
                if asyncio.iscoroutine(result):
                    health = await result
                else:
                    health = result  # type: ignore[assignment]
                await self.check_and_alert(health)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("HealthAlerter.run_loop check error: %s", exc)
            await asyncio.sleep(interval_s)

    async def check_and_alert(self, health: dict[str, Any]) -> None:
        """
        Called by the health monitor after each check.

        Sends an alert if overall != 'healthy' for *threshold_failures*
        consecutive checks.
        """
        self._total_checks += 1
        self._last_check_at = time.time()
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

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_checks": self._total_checks,
            "consecutive_failures": self._consecutive_failures,
            "alerts_sent": self._total_alerts_sent,
            "total_alerts_sent": self._total_alerts_sent,
            "last_check_at": self._last_check_at,
            "threshold": self._threshold,
        }
