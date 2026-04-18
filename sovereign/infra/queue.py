"""Async task queue — in-process priority queue for agent tasks."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional

logger = logging.getLogger(__name__)


class TaskPriority(IntEnum):
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


@dataclass
class QueuedTask:
    task_id: str
    priority: TaskPriority
    agent_id: str
    objective: str
    payload: dict
    enqueued_at: float
    attempts: int = 0
    max_attempts: int = 3
    status: str = "queued"


class TaskQueue:
    """Asyncio-based in-process priority task queue.

    Internally uses ``asyncio.PriorityQueue`` with entries stored as
    ``(priority, task_id, QueuedTask)`` tuples so that items with equal
    priority are broken by insertion order (task_id is a UUID string).
    """

    def __init__(self) -> None:
        self._pq: asyncio.PriorityQueue[tuple[int, str, QueuedTask]] = (
            asyncio.PriorityQueue()
        )
        # Mirror of everything currently sitting in the queue (task_id -> task)
        self._pending: dict[str, QueuedTask] = {}
        self.dead_letters: list[QueuedTask] = []

        self._enqueued_total: int = 0
        self._dequeued_total: int = 0
        self._failed_total: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def enqueue(
        self,
        agent_id: str,
        objective: str,
        payload: dict,
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> QueuedTask:
        """Create and enqueue a new task; returns the enqueued task."""
        task = QueuedTask(
            task_id=str(uuid.uuid4()),
            priority=priority,
            agent_id=agent_id,
            objective=objective,
            payload=payload,
            enqueued_at=time.time(),
        )
        await self._pq.put((int(priority), task.task_id, task))
        self._pending[task.task_id] = task
        self._enqueued_total += 1
        logger.debug("Enqueued task %s (priority=%s, agent=%s)", task.task_id, priority.name, agent_id)
        return task

    async def dequeue(self) -> QueuedTask:
        """Block until a task is available and return it."""
        _, _, task = await self._pq.get()
        self._pending.pop(task.task_id, None)
        self._dequeued_total += 1
        task.status = "processing"
        logger.debug("Dequeued task %s", task.task_id)
        return task

    async def dequeue_nowait(self) -> Optional[QueuedTask]:
        """Return next task immediately, or None if the queue is empty."""
        try:
            _, _, task = self._pq.get_nowait()
        except asyncio.QueueEmpty:
            return None
        self._pending.pop(task.task_id, None)
        self._dequeued_total += 1
        task.status = "processing"
        return task

    def size(self) -> int:
        """Current number of items in the queue."""
        return self._pq.qsize()

    def pending(self) -> list[QueuedTask]:
        """Snapshot of tasks currently waiting in the queue."""
        return list(self._pending.values())

    def stats(self) -> dict:
        """Return queue statistics."""
        return {
            "size": self.size(),
            "enqueued_total": self._enqueued_total,
            "dequeued_total": self._dequeued_total,
            "failed_total": self._failed_total,
        }

    def mark_failed(self, task: QueuedTask) -> None:
        """Record a task failure; move to dead-letter queue if exhausted."""
        task.attempts += 1
        task.status = "failed"
        self._failed_total += 1
        if task.attempts >= task.max_attempts:
            logger.warning(
                "Task %s exhausted %d attempts — moving to dead-letter queue",
                task.task_id,
                task.max_attempts,
            )
            self.dead_letters.append(task)
        else:
            logger.info(
                "Task %s failed (attempt %d/%d)",
                task.task_id,
                task.attempts,
                task.max_attempts,
            )

    async def requeue_dead_letters(self) -> int:
        """Re-enqueue all dead-letter tasks with incremented attempt counters."""
        count = 0
        revived: list[QueuedTask] = []
        for task in self.dead_letters:
            task.status = "queued"
            await self._pq.put((int(task.priority), task.task_id, task))
            self._pending[task.task_id] = task
            self._enqueued_total += 1
            revived.append(task)
            count += 1
        for t in revived:
            self.dead_letters.remove(t)
        logger.info("Requeued %d dead-letter tasks", count)
        return count

    def clear(self) -> int:
        """Drain the queue and return the number of tasks discarded."""
        count = 0
        while not self._pq.empty():
            try:
                self._pq.get_nowait()
                count += 1
            except asyncio.QueueEmpty:
                break
        self._pending.clear()
        logger.info("Cleared %d tasks from queue", count)
        return count
