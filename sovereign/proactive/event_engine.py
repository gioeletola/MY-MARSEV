"""Event engine — schedules and fires time/condition-based proactive events."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

AsyncCallback = Callable[[], Awaitable[None]]


@dataclass
class ProactiveEvent:
    event_id: str
    name: str
    trigger_at: float
    callback_name: str
    recurring_s: float = 0.0
    enabled: bool = True
    last_fired_at: float = 0.0
    fire_count: int = 0


class EventEngine:
    """
    Fires registered async callbacks at scheduled times.
    Supports one-shot and recurring events.
    """

    def __init__(self) -> None:
        self._events: dict[str, ProactiveEvent] = {}
        self._callbacks: dict[str, AsyncCallback] = {}
        self._running = False

    def schedule(
        self,
        event_id: str,
        name: str,
        callback: AsyncCallback,
        delay_s: float = 0.0,
        recurring_s: float = 0.0,
    ) -> ProactiveEvent:
        event = ProactiveEvent(
            event_id=event_id,
            name=name,
            trigger_at=time.time() + delay_s,
            callback_name=event_id,
            recurring_s=recurring_s,
        )
        self._events[event_id] = event
        self._callbacks[event_id] = callback
        return event

    def cancel(self, event_id: str) -> bool:
        if event_id in self._events:
            del self._events[event_id]
            self._callbacks.pop(event_id, None)
            return True
        return False

    async def run_loop(self, stop_event: asyncio.Event | None = None) -> None:
        self._running = True
        logger.info("EventEngine started")
        while self._running:
            if stop_event and stop_event.is_set():
                break
            now = time.time()
            for event in list(self._events.values()):
                if not event.enabled:
                    continue
                if now >= event.trigger_at:
                    cb = self._callbacks.get(event.event_id)
                    if cb:
                        try:
                            await cb()
                        except Exception as exc:
                            logger.error("EventEngine: %s callback failed: %s", event.event_id, exc)
                    event.last_fired_at = now
                    event.fire_count += 1
                    if event.recurring_s > 0:
                        event.trigger_at = now + event.recurring_s
                    else:
                        del self._events[event.event_id]
            await asyncio.sleep(1.0)

    def stop(self) -> None:
        self._running = False

    def list_events(self) -> list[dict]:
        return [e.__dict__ for e in self._events.values()]
