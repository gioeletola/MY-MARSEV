"""Wake-word trigger — listens continuously for a keyword to activate the system."""
from __future__ import annotations

import asyncio
import logging
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

Callback = Callable[[], Awaitable[None]]


class WakeTrigger:
    """
    Watches for a wake word (e.g. "hey sovereign") and fires a callback.
    Real implementation: pvporcupine or openwakeword library.
    Stub here for interface parity.
    """

    def __init__(self, wake_word: str = "hey sovereign", sensitivity: float = 0.5) -> None:
        self._wake_word = wake_word.lower()
        self._sensitivity = sensitivity
        self._active = False
        self._callbacks: list[Callback] = []
        self._available = False
        try:
            import pvporcupine  # type: ignore
            self._available = True
        except ImportError:
            logger.debug("pvporcupine not installed — WakeTrigger in stub mode")

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
