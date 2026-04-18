"""H24 worker pool — manages long-running background workers with auto-restart."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)


class WorkerStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    FAILED = "failed"
    STOPPED = "stopped"
    RESTARTING = "restarting"


@dataclass
class WorkerSpec:
    worker_id: str
    coro_factory: Callable[[], Awaitable[None]]
    restart_on_failure: bool = True
    max_restarts: int = 10
    restart_delay_s: float = 2.0
    description: str = ""


@dataclass
class WorkerState:
    spec: WorkerSpec
    status: WorkerStatus = WorkerStatus.IDLE
    task: asyncio.Task | None = None
    restarts: int = 0
    started_at: float = 0.0
    last_failure_at: float = 0.0
    last_error: str = ""


class WorkerManager:
    """
    Manages a pool of asyncio background workers.
    Workers that crash are automatically restarted (up to max_restarts).
    """

    def __init__(self) -> None:
        self._workers: dict[str, WorkerState] = {}
        self._stop_event = asyncio.Event()

    def register(self, spec: WorkerSpec) -> None:
        if spec.worker_id in self._workers:
            return
        self._workers[spec.worker_id] = WorkerState(spec=spec)
        logger.debug("Registered worker: %s", spec.worker_id)

    async def start(self, worker_id: str) -> None:
        state = self._workers.get(worker_id)
        if state is None:
            raise KeyError(f"Unknown worker: {worker_id}")
        if state.status == WorkerStatus.RUNNING:
            return
        await self._spawn(state)

    async def start_all(self) -> None:
        for wid in self._workers:
            await self.start(wid)

    async def stop(self, worker_id: str) -> None:
        state = self._workers.get(worker_id)
        if state and state.task and not state.task.done():
            state.task.cancel()
            try:
                await state.task
            except (asyncio.CancelledError, Exception):
                pass
            state.status = WorkerStatus.STOPPED

    async def stop_all(self) -> None:
        self._stop_event.set()
        for wid in list(self._workers):
            await self.stop(wid)

    async def _spawn(self, state: WorkerState) -> None:
        state.status = WorkerStatus.RUNNING
        state.started_at = time.time()
        state.task = asyncio.create_task(self._run_with_restart(state))

    async def _run_with_restart(self, state: WorkerState) -> None:
        spec = state.spec
        while not self._stop_event.is_set():
            try:
                logger.info("Worker %s starting", spec.worker_id)
                await spec.coro_factory()
                logger.info("Worker %s finished normally", spec.worker_id)
                state.status = WorkerStatus.IDLE
                return
            except asyncio.CancelledError:
                state.status = WorkerStatus.STOPPED
                return
            except Exception as exc:
                state.last_failure_at = time.time()
                state.last_error = str(exc)
                state.restarts += 1
                logger.error("Worker %s crashed (%s): %s", spec.worker_id, state.restarts, exc)
                if not spec.restart_on_failure or state.restarts >= spec.max_restarts:
                    state.status = WorkerStatus.FAILED
                    logger.critical("Worker %s permanently failed after %d restarts", spec.worker_id, state.restarts)
                    return
                state.status = WorkerStatus.RESTARTING
                delay = min(spec.restart_delay_s * (2 ** min(state.restarts - 1, 5)), 300.0)
                logger.info("Worker %s restarting in %.1fs", spec.worker_id, delay)
                await asyncio.sleep(delay)

    def status(self, worker_id: str) -> WorkerStatus | None:
        state = self._workers.get(worker_id)
        return state.status if state else None

    def snapshot(self) -> list[dict]:
        result = []
        for wid, state in self._workers.items():
            result.append({
                "worker_id": wid,
                "description": state.spec.description,
                "status": state.status.value,
                "restarts": state.restarts,
                "started_at": state.started_at,
                "last_error": state.last_error,
            })
        return result

    def failed_workers(self) -> list[str]:
        return [wid for wid, s in self._workers.items() if s.status == WorkerStatus.FAILED]


# ---------------------------------------------------------------------------
# H24 Worker Pool
# ---------------------------------------------------------------------------


class H24WorkerPool:
    """Keeps N workers running continuously; auto-restarts crashed workers.

    Workers drain items from *task_queue* (any object with an async ``get``
    method, e.g. ``asyncio.Queue``).  When a worker raises an unhandled
    exception the crash is counted and the loop continues immediately.
    """

    def __init__(
        self,
        n_workers: int = 3,
        task_queue: asyncio.Queue | None = None,  # type: ignore[type-arg]
    ) -> None:
        self._n = n_workers
        self._queue = task_queue
        self._workers: list[asyncio.Task] = []  # type: ignore[type-arg]
        self._stats: dict[str, int] = {
            "started": 0,
            "crashed": 0,
            "restarted": 0,
        }

    async def start(self, stop_event: asyncio.Event) -> None:
        """Launch all workers and supervise them until *stop_event* is set."""
        self._workers = []
        for worker_id in range(self._n):
            task = asyncio.create_task(
                self._worker_loop(worker_id, stop_event),
                name=f"h24_worker_{worker_id}",
            )
            self._workers.append(task)
            self._stats["started"] += 1

        # Wait for all workers (they only exit when stop_event fires)
        await asyncio.gather(*self._workers, return_exceptions=True)

    async def _worker_loop(self, worker_id: int, stop_event: asyncio.Event) -> None:
        """Drain queue items; on exception log and increment stats, then continue."""
        logger.info("H24WorkerPool: worker %d started", worker_id)
        while not stop_event.is_set():
            try:
                if self._queue is not None:
                    try:
                        item = await asyncio.wait_for(
                            self._queue.get(), timeout=1.0
                        )
                        # Process item — subclasses / callers can patch _process
                        await self._process(worker_id, item)
                        self._queue.task_done()
                    except asyncio.TimeoutError:
                        continue
                else:
                    # No queue supplied — idle loop
                    await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._stats["crashed"] += 1
                self._stats["restarted"] += 1
                logger.error(
                    "H24WorkerPool: worker %d crashed: %s — restarting",
                    worker_id,
                    exc,
                )
                # Brief back-off before continuing
                await asyncio.sleep(0.1)

    async def _process(self, worker_id: int, item: object) -> None:  # noqa: ARG002
        """Override in subclasses to handle queue items."""

    def get_stats(self) -> dict[str, int]:
        """Return a snapshot of pool statistics."""
        return dict(self._stats)
