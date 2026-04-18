"""Silent ops — background tasks that run without user interaction."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

AsyncTask = Callable[[], Awaitable[None]]


@dataclass
class SilentTask:
    task_id: str
    name: str
    interval_s: float
    callback: AsyncTask
    enabled: bool = True
    last_run_at: float = 0.0
    run_count: int = 0
    error_count: int = 0
    last_error: str = ""


class SilentOps:
    """
    Runs low-priority background tasks silently (no user notification by default).
    Examples: memory cleanup, index updates, stale data purge, cache warming.
    """

    def __init__(self) -> None:
        self._tasks: dict[str, SilentTask] = {}
        self._running = False

    def register(self, task: SilentTask) -> None:
        self._tasks[task.task_id] = task

    def enable(self, task_id: str) -> None:
        if t := self._tasks.get(task_id):
            t.enabled = True

    def disable(self, task_id: str) -> None:
        if t := self._tasks.get(task_id):
            t.enabled = False

    async def run_loop(self, stop_event: asyncio.Event | None = None) -> None:
        self._running = True
        logger.info("SilentOps started with %d tasks", len(self._tasks))
        while self._running:
            if stop_event and stop_event.is_set():
                break
            now = time.time()
            for task in self._tasks.values():
                if not task.enabled:
                    continue
                if now - task.last_run_at >= task.interval_s:
                    try:
                        await task.callback()
                        task.last_run_at = now
                        task.run_count += 1
                    except Exception as exc:
                        task.error_count += 1
                        task.last_error = str(exc)
                        logger.warning("SilentOps task %s failed: %s", task.task_id, exc)
            await asyncio.sleep(5.0)

    def stop(self) -> None:
        self._running = False

    def snapshot(self) -> list[dict]:
        return [
            {
                "task_id": t.task_id, "name": t.name, "enabled": t.enabled,
                "interval_s": t.interval_s, "last_run_at": t.last_run_at,
                "run_count": t.run_count, "error_count": t.error_count,
            }
            for t in self._tasks.values()
        ]
