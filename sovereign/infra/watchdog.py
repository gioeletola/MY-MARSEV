"""Process watchdog — supervises coroutines and restarts them on failure."""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Coroutine
from typing import Any

logger = logging.getLogger(__name__)

_MAX_BACKOFF_S = 300.0


class ProcessWatchdog:
    """Monitors coroutines; alerts and restarts on failure with exponential backoff."""

    def __init__(self, alert_callback: Callable[[str, Exception], Any] | None = None) -> None:
        # name → {factory, task, restart_count, last_fail, last_error}
        self._registry: dict[str, dict[str, Any]] = {}
        self._alert_callback = alert_callback

    def register(self, name: str, factory: Callable[[], Coroutine[Any, Any, Any]]) -> None:
        """Register a coroutine factory under *name*."""
        if name in self._registry:
            logger.warning("ProcessWatchdog: '%s' already registered — overwriting", name)
        self._registry[name] = {
            "factory": factory,
            "task": None,
            "restart_count": 0,
            "last_fail": 0.0,
            "last_error": "",
        }
        logger.debug("ProcessWatchdog: registered '%s'", name)

    async def start_all(self, stop_event: asyncio.Event) -> None:
        """Start supervision for all registered coroutines."""
        supervisors = [
            asyncio.create_task(self._supervise(name, stop_event))
            for name in self._registry
        ]
        if supervisors:
            await asyncio.gather(*supervisors, return_exceptions=True)

    async def _supervise(self, name: str, stop_event: asyncio.Event) -> None:
        """Supervise a single coroutine; restart with exponential backoff on failure."""
        entry = self._registry[name]
        while not stop_event.is_set():
            try:
                logger.info("ProcessWatchdog: starting '%s'", name)
                coro = entry["factory"]()
                entry["task"] = asyncio.create_task(coro)
                await entry["task"]
                logger.info("ProcessWatchdog: '%s' finished normally", name)
                return
            except asyncio.CancelledError:
                logger.info("ProcessWatchdog: '%s' cancelled", name)
                return
            except Exception as exc:
                entry["restart_count"] += 1
                entry["last_fail"] = time.time()
                entry["last_error"] = str(exc)
                logger.error(
                    "ProcessWatchdog: '%s' crashed (restart #%d): %s",
                    name,
                    entry["restart_count"],
                    exc,
                )
                # Alert callback
                if self._alert_callback is not None:
                    try:
                        result = self._alert_callback(name, exc)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as cb_exc:
                        logger.warning(
                            "ProcessWatchdog: alert_callback failed: %s", cb_exc
                        )

                if stop_event.is_set():
                    return

                # Exponential backoff capped at _MAX_BACKOFF_S
                backoff = min(2 ** (entry["restart_count"] - 1), _MAX_BACKOFF_S)
                logger.info(
                    "ProcessWatchdog: restarting '%s' in %.1fs", name, backoff
                )
                try:
                    await asyncio.wait_for(
                        asyncio.shield(stop_event.wait()), timeout=backoff
                    )
                    # stop_event fired during backoff
                    return
                except asyncio.TimeoutError:
                    pass

    def get_status(self) -> dict[str, dict[str, Any]]:
        """Return a snapshot of the watchdog registry."""
        result: dict[str, dict[str, Any]] = {}
        for name, entry in self._registry.items():
            task = entry.get("task")
            if task is None:
                task_state = "not_started"
            elif task.done():
                task_state = "done"
            elif task.cancelled():
                task_state = "cancelled"
            else:
                task_state = "running"
            result[name] = {
                "task_state": task_state,
                "restart_count": entry["restart_count"],
                "last_fail": entry["last_fail"],
                "last_error": entry["last_error"],
            }
        return result
