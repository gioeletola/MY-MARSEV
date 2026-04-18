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
# H24 Worker Pool — always-on workers with auto-restart
# ---------------------------------------------------------------------------

class H24WorkerPool:
    """Keeps N workers running 24/7; auto-restarts crashed workers."""

    def __init__(
        self,
        n_workers: int = 3,
        task_queue: asyncio.Queue[Any] | None = None,
        monitor_interval_s: float = 0.1,
    ) -> None:
        self._workers: list[asyncio.Task[None]] = []
        self._n = n_workers
        self._queue: asyncio.Queue[Any] = task_queue or asyncio.Queue()
        self._monitor_interval = monitor_interval_s
        self._stats: dict[str, int] = {
            "started": 0,
            "crashed": 0,
            "restarted": 0,
        }

    async def start(self, stop_event: asyncio.Event) -> None:
        """Launch N workers; monitor and restart any that crash."""
        for i in range(self._n):
            task = asyncio.create_task(self._worker_loop(i, stop_event))
            self._workers.append(task)
            self._stats["started"] += 1
            logger.info("H24WorkerPool: worker-%d started", i)

        # Monitor loop — restart crashed workers until stop_event is set
        while not stop_event.is_set():
            for idx, task in enumerate(self._workers):
                if task.done() and not stop_event.is_set():
                    exc = task.exception() if not task.cancelled() else None
                    if exc is not None:
                        self._stats["crashed"] += 1
                        logger.error(
                            "H24WorkerPool: worker-%d crashed: %s — restarting", idx, exc
                        )
                    self._stats["restarted"] += 1
                    new_task = asyncio.create_task(
                        self._worker_loop(idx, stop_event)
                    )
                    self._workers[idx] = new_task
                    self._stats["started"] += 1
            try:
                await asyncio.wait_for(
                    asyncio.shield(stop_event.wait()),
                    timeout=self._monitor_interval,
                )
            except asyncio.TimeoutError:
                pass

        # Cancel all remaining workers
        for task in self._workers:
            if not task.done():
                task.cancel()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        logger.info("H24WorkerPool: all workers stopped")

    async def _worker_loop(
        self, worker_id: int, stop_event: asyncio.Event
    ) -> None:
        """Drain task_queue until stop_event fires; on unhandled crash bubble up."""
        logger.debug("H24WorkerPool: worker-%d loop running", worker_id)
        while not stop_event.is_set():
            try:
                task = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                logger.debug("H24WorkerPool: worker-%d processing task", worker_id)
                if callable(task):
                    result = task()
                    if asyncio.iscoroutine(result):
                        await result
                self._queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                return
            except Exception as exc:
                logger.error(
                    "H24WorkerPool: worker-%d task error: %s", worker_id, exc
                )
                # Signal crash so monitor loop can restart
                raise

    def get_stats(self) -> dict[str, int]:
        return dict(self._stats)
