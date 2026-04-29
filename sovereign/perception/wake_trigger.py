"""Wake-word trigger — listens continuously for a keyword to activate the system."""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)

Callback = Callable[[], Awaitable[None]]


_DEFAULT_PHRASES: list[str] = [
    "hey sovereign",
    "sovereign",
    "marsev",
    "ok sovereign",
]


class WakeTrigger:
    """
    Watches for a wake word (e.g. "hey sovereign") and fires a callback.
    Real implementation: pvporcupine or openwakeword library.
    Stub here for interface parity.

    Supports multiple wake phrases and simple text-based matching via
    :meth:`matches` — no audio hardware required.
    """

    def __init__(self, wake_word: str = "hey sovereign", sensitivity: float = 0.5) -> None:
        self._sensitivity = sensitivity
        self._active = False
        self._callbacks: list[Callback] = []
        self._available = False
        # Phrase registry — start with defaults then add the constructor word
        self._phrases: list[str] = list(_DEFAULT_PHRASES)
        if wake_word.lower() not in self._phrases:
            self._phrases.append(wake_word.lower())
        try:
            import pvporcupine  # type: ignore
            self._available = True
        except ImportError:
            logger.debug("pvporcupine not installed — WakeTrigger in stub mode")

    # ── Phrase management ──────────────────────────────────────────────────

    @property
    def phrases(self) -> list[str]:
        """Return the current list of registered wake phrases."""
        return list(self._phrases)

    def add_phrase(self, phrase: str) -> None:
        """Register a custom wake phrase (case-insensitive)."""
        p = phrase.lower().strip()
        if p and p not in self._phrases:
            self._phrases.append(p)
            logger.debug("WakeTrigger: added phrase %r", p)

    def remove_phrase(self, phrase: str) -> bool:
        """Remove a wake phrase. Returns True if it existed."""
        p = phrase.lower().strip()
        if p in self._phrases:
            self._phrases.remove(p)
            logger.debug("WakeTrigger: removed phrase %r", p)
            return True
        return False

    def matches(self, text: str) -> bool:
        """Return True if *text* contains any registered wake phrase.

        Comparison is case-insensitive and ignores leading/trailing whitespace.
        """
        lowered = text.lower()
        return any(phrase in lowered for phrase in self._phrases)

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def on_wake(self, callback: Callback) -> None:
        self._callbacks.append(callback)

    async def start(self) -> None:
        self._active = True
        if self._available:
            await self._hardware_loop()
        else:
            logger.info("WakeTrigger stub: no wake-word detection active")

    async def stop(self) -> None:
        self._active = False

    async def _hardware_loop(self) -> None:
        while self._active:
            await asyncio.sleep(0.1)

    async def simulate_wake(self) -> None:
        """For testing only — simulate a wake event."""
        logger.info("WakeTrigger: simulated wake event")
        for cb in self._callbacks:
            await cb()

    @property
    def active(self) -> bool:
        return self._active
