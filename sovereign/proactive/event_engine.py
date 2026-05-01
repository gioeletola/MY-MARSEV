"""EventEngine — publish/subscribe internal event bus with replay and stats."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

_MAX_HISTORY = 10_000


@dataclass
class Event:
    event_type: str
    source: str
    data: dict[str, Any] = field(default_factory=dict)
    priority: float = 0.5        # 0.0 (low) – 1.0 (critical)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    timestamp: float = field(default_factory=time.time)

    @property
    def iso_timestamp(self) -> str:
        return datetime.fromtimestamp(self.timestamp, tz=timezone.utc).isoformat()


AsyncCallback = Callable[[Event], Coroutine[Any, Any, None]]


class EventEngine:
    """
    Lightweight async event bus for the SOVEREIGN OS.

    Features:
    - subscribe(event_type, async_callback) — register listener
    - publish(event_type, source, data, priority) — dispatch to subscribers
    - replay(since_iso) — fetch historical events
    - stats() — event rate + breakdown by type
    """

    def __init__(self, max_history: int = _MAX_HISTORY) -> None:
        self._subscribers: dict[str, list[AsyncCallback]] = defaultdict(list)
        self._wildcard: list[AsyncCallback] = []
        self._history: deque[Event] = deque(maxlen=max_history)
        self._counts: dict[str, int] = defaultdict(int)
        self._start_time = time.time()

    # ------------------------------------------------------------------
    # Subscribe
    # ------------------------------------------------------------------

    def subscribe(self, event_type: str | None, callback: AsyncCallback) -> None:
        """Register *callback* for *event_type* (None = all events)."""
        if event_type is None:
            self._wildcard.append(callback)
        else:
            self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str | None, callback: AsyncCallback) -> bool:
        try:
            if event_type is None:
                self._wildcard.remove(callback)
            else:
                self._subscribers[event_type].remove(callback)
            return True
        except ValueError:
            return False

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    async def publish(
        self,
        event_type: str,
        source: str,
        data: dict[str, Any] | None = None,
        priority: float = 0.5,
    ) -> Event:
        event = Event(event_type=event_type, source=source, data=data or {}, priority=priority)
        self._history.append(event)
        self._counts[event_type] += 1

        targets = self._subscribers.get(event_type, []) + self._wildcard
        if targets:
            results = await asyncio.gather(
                *(cb(event) for cb in targets),
                return_exceptions=True,
            )
            for r in results:
                if isinstance(r, Exception):
                    logger.warning("EventEngine: subscriber error: %s", r)

        return event

    def publish_sync(
        self,
        event_type: str,
        source: str,
        data: dict[str, Any] | None = None,
        priority: float = 0.5,
    ) -> Event:
        """Fire-and-forget publish for sync contexts (no await on callbacks)."""
        event = Event(event_type=event_type, source=source, data=data or {}, priority=priority)
        self._history.append(event)
        self._counts[event_type] += 1
        return event

    # ------------------------------------------------------------------
    # Replay
    # ------------------------------------------------------------------

    def replay(self, since_iso: str | None = None) -> list[Event]:
        """Return all stored events, optionally filtered to since_iso."""
        if since_iso is None:
            return list(self._history)
        since_ts = datetime.fromisoformat(since_iso).timestamp()
        return [e for e in self._history if e.timestamp >= since_ts]

    def recent(self, n: int = 50) -> list[Event]:
        events = list(self._history)
        return events[-n:]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        elapsed = max(time.time() - self._start_time, 1)
        total = sum(self._counts.values())
        return {
            "total_events": total,
            "events_per_minute": round(total / elapsed * 60, 2),
            "by_type": dict(self._counts),
            "subscribers": {k: len(v) for k, v in self._subscribers.items()},
            "history_size": len(self._history),
        }

    async def run_loop(self, stop_event: asyncio.Event | None = None) -> None:
        """Background loop — waits for stop signal. EventEngine is event-driven."""
        if stop_event is not None:
            await stop_event.wait()
        else:
            await asyncio.Event().wait()

    def stop(self) -> None:
        pass

    def reset(self) -> None:
        self._history.clear()
        self._counts.clear()
        self._start_time = time.time()


# Module-level singleton
_engine: EventEngine | None = None


def get_event_engine() -> EventEngine:
    global _engine
    if _engine is None:
        _engine = EventEngine()
    return _engine
