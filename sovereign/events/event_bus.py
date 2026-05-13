"""
Async pub/sub EventBus for SOVEREIGN AI OS.

Supports:
  - Typed subscriptions (subscribe to specific EventType values)
  - Wildcard subscription (subscribe to ALL events)
  - Both sync and async subscriber callbacks
  - Subscriber isolation (one slow subscriber won't block others)
  - Thread-safe registration from sync contexts
"""
from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Callable, Coroutine

from sovereign.events.event_types import EventType, SovereignEvent

logger = logging.getLogger(__name__)

# A subscriber is any callable that accepts a SovereignEvent.
# It may be sync (returns None) or async (returns a Coroutine).
Subscriber = Callable[[SovereignEvent], Any]

# Sentinel for wildcard subscriptions
_ALL = object()


class EventBus:
    """
    Central event bus — singleton per orchestrator instance.

    Usage::

        bus = EventBus()

        # Subscribe to a specific event type (sync callback)
        def on_task(event: SovereignEvent):
            print(event.data)
        bus.subscribe(EventType.TASK_START, on_task)

        # Subscribe to all events (async callback)
        async def on_any(event: SovereignEvent):
            await log_event(event)
        bus.subscribe_all(on_any)

        # Emit (fire-and-forget, non-blocking)
        bus.emit(SovereignEvent(type=EventType.TASK_START, session_id="abc",
                                data={"agent": "finance_os_chief"}))

        # Unsubscribe
        bus.unsubscribe(EventType.TASK_START, on_task)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # topic → list of subscribers; _ALL key = wildcard
        self._subscribers: dict[Any, list[Subscriber]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def subscribe(self, event_type: EventType, callback: Subscriber) -> None:
        """Subscribe to a specific event type."""
        with self._lock:
            self._subscribers.setdefault(event_type, [])
            if callback not in self._subscribers[event_type]:
                self._subscribers[event_type].append(callback)

    def subscribe_all(self, callback: Subscriber) -> None:
        """Subscribe to every event type (wildcard)."""
        with self._lock:
            self._subscribers.setdefault(_ALL, [])
            if callback not in self._subscribers[_ALL]:
                self._subscribers[_ALL].append(callback)

    def unsubscribe(self, event_type: EventType, callback: Subscriber) -> None:
        """Unsubscribe from a specific event type."""
        with self._lock:
            subs = self._subscribers.get(event_type, [])
            if callback in subs:
                subs.remove(callback)

    def unsubscribe_all(self, callback: Subscriber) -> None:
        """Unsubscribe a wildcard subscriber."""
        with self._lock:
            subs = self._subscribers.get(_ALL, [])
            if callback in subs:
                subs.remove(callback)

    # ------------------------------------------------------------------
    # Emission
    # ------------------------------------------------------------------

    def emit(self, event: SovereignEvent) -> None:
        """
        Emit an event synchronously.

        Sync subscribers are called inline.
        Async subscribers are scheduled on the running event loop if available,
        otherwise dropped with a warning (they require an async context).
        """
        with self._lock:
            targets = (
                list(self._subscribers.get(event.type, []))
                + list(self._subscribers.get(_ALL, []))
            )

        loop = self._get_loop()
        for cb in targets:
            try:
                result = cb(event)
                if asyncio.iscoroutine(result):
                    if loop and loop.is_running():
                        asyncio.ensure_future(result, loop=loop)
                    else:
                        logger.warning(
                            "EventBus: async subscriber %s called outside event loop", cb
                        )
            except Exception as exc:
                logger.error("EventBus subscriber %s raised: %s", cb, exc)

    async def emit_async(self, event: SovereignEvent) -> None:
        """
        Emit and await all async subscribers concurrently.
        Sync subscribers are called inline before awaiting.
        """
        with self._lock:
            targets = (
                list(self._subscribers.get(event.type, []))
                + list(self._subscribers.get(_ALL, []))
            )

        coros: list[Coroutine] = []
        for cb in targets:
            try:
                result = cb(event)
                if asyncio.iscoroutine(result):
                    coros.append(result)
            except Exception as exc:
                logger.error("EventBus sync subscriber %s raised: %s", cb, exc)

        if coros:
            results = await asyncio.gather(*coros, return_exceptions=True)
            for i, r in enumerate(results):
                if isinstance(r, Exception):
                    logger.error("EventBus async subscriber raised: %s", r)

    # ------------------------------------------------------------------
    # Legacy bridge — accepts the old raw-dict callback style
    # ------------------------------------------------------------------

    def add_legacy_callback(self, cb: Callable[[dict[str, Any]], None]) -> None:
        """
        Register an old-style dict callback.
        Wraps it so it receives SovereignEvent.to_dict() on every event.
        """
        def _wrapper(event: SovereignEvent) -> None:
            cb(event.to_dict())
        # Store the wrapper keyed by the original callback for removal
        with self._lock:
            if not hasattr(self, "_legacy_map"):
                self._legacy_map: dict[int, Subscriber] = {}
            self._legacy_map[id(cb)] = _wrapper
        self.subscribe_all(_wrapper)

    def remove_legacy_callback(self, cb: Callable[[dict[str, Any]], None]) -> None:
        """Remove an old-style dict callback registered via add_legacy_callback."""
        with self._lock:
            if not hasattr(self, "_legacy_map"):
                return
            wrapper = self._legacy_map.pop(id(cb), None)
        if wrapper:
            self.unsubscribe_all(wrapper)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Bind to a specific event loop (call from lifespan startup)."""
        self._loop = loop

    def _get_loop(self) -> asyncio.AbstractEventLoop | None:
        if self._loop and not self._loop.is_closed():
            return self._loop
        try:
            return asyncio.get_event_loop()
        except RuntimeError:
            return None

    def subscriber_count(self, event_type: EventType | None = None) -> int:
        """Return number of subscribers (for a type, or total across all types)."""
        with self._lock:
            if event_type is not None:
                return len(self._subscribers.get(event_type, []))
            return sum(len(v) for v in self._subscribers.values())
