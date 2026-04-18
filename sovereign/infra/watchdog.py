"""Process watchdog — supervises named coroutines with exponential-backoff restart."""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Coroutine
from typing import Any

logger = logging.getLogger(__name__)


class ProcessWatchdog:
    """Supervises named coroutines; restarts on crash with exponential back-off.

    Usage::

        wd = ProcessWatchdog(alert_callback=my_alert_fn)
        wd.register("poller", lambda: some_polling_coroutine())
        stop = asyncio.Event()
        await wd.start_all(stop)   # blocks until stop is set
    """

    def __init__(self, alert_callback: Callable[[str, Exception], Any] | None = None) -> None:
        # name → {factory, restart_count, last_fail, status}
        self._registry: dict[str, dict[str, Any]] = {}
        self._alert_cb = alert_callback

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        factory: Callable[[], Coroutine[Any, Any, Any]],
    ) -> None:
        """Register a coroutine factory under *name*."""
        self._registry[name] = {
            "factory": factory,
            "restart_count": 0,
            "last_fail": None,
            "status": "registered",
        }
        logger.debug("ProcessWatchdog: registered %s", name)

    async def start_all(self, stop_event: asyncio.Event) -> None:
        """Start all registered coroutines and supervise them."""
        if not self._registry:
            return
        tasks = [
            asyncio.create_task(
                self._supervise(name, entry["factory"], stop_event),
                name=f"watchdog_{name}",
            )
            for name, entry in self._registry.items()
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _supervise(
        self,
        name: str,
        factory: Callable[[], Coroutine[Any, Any, Any]],
        stop_event: asyncio.Event,
    ) -> None:
        """Run *factory()* in a loop; restart with exp back-off on crash."""
        entry = self._registry[name]
        entry["status"] = "running"

        while not stop_event.is_set():
            try:
                logger.info("ProcessWatchdog: starting %s", name)
                await factory()
                # Coroutine finished normally
                if stop_event.is_set():
                    entry["status"] = "stopped"
                    return
                logger.info("ProcessWatchdog: %s exited normally — restarting", name)
            except asyncio.CancelledError:
                entry["status"] = "stopped"
                return
            except Exception as exc:
                entry["restart_count"] += 1
                entry["last_fail"] = time.time()
                entry["status"] = "restarting"
                logger.error(
                    "ProcessWatchdog: %s crashed (%d): %s",
                    name,
                    entry["restart_count"],
                    exc,
                )
                if self._alert_cb is not None:
                    try:
                        self._alert_cb(name, exc)
                    except Exception:
                        pass

                delay = min(2 ** entry["restart_count"], 300)
                logger.info(
                    "ProcessWatchdog: %s back-off %.0fs before restart", name, delay
                )
                try:
                    await asyncio.wait_for(
                        asyncio.shield(stop_event.wait()), timeout=delay
                    )
                except asyncio.TimeoutError:
                    pass
                if stop_event.is_set():
                    entry["status"] = "stopped"
                    return
                entry["status"] = "running"

    def get_status(self) -> dict[str, dict[str, Any]]:
        """Return {name: {restart_count, last_fail, status}} for every registered coroutine."""
        return {
            name: {
                "restart_count": entry["restart_count"],
                "last_fail": entry["last_fail"],
                "status": entry["status"],
            }
            for name, entry in self._registry.items()
        }
