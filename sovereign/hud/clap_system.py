"""Clap system — double-clap or sound-spike detection to activate the HUD."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)

Callback = Callable[[], Awaitable[None]]


class ClapSystem:
    """
    Listens for two rapid audio spikes (claps) within a time window.
    Fires a callback on detection.

    Real implementation requires pyaudio. Stub here for interface parity.
    """

    def __init__(
        self,
        threshold: float = 0.8,
        window_s: float = 0.5,
        cooldown_s: float = 2.0,
    ) -> None:
        self._threshold = threshold
        self._window_s = window_s
        self._cooldown_s = cooldown_s
        self._last_spike: float = 0.0
        self._last_fire: float = 0.0
        self._callbacks: list[Callback] = []
        self._active = False
        self._available = False
        try:
            import pyaudio  # type: ignore
            self._available = True
        except ImportError:
            logger.debug("pyaudio not available — ClapSystem in stub mode")

    def on_clap(self, callback: Callback) -> None:
        self._callbacks.append(callback)

    async def start(self) -> None:
        self._active = True
        if self._available:
            await asyncio.get_event_loop().run_in_executor(None, self._listen_blocking)
        else:
            logger.info("ClapSystem stub: no audio detection active")

    async def stop(self) -> None:
        self._active = False

    def _listen_blocking(self) -> None:
        import math  # type: ignore
        import struct

        import pyaudio
        pa = pyaudio.PyAudio()
        stream = pa.open(format=pyaudio.paInt16, channels=1, rate=44100,
                         input=True, frames_per_buffer=1024)
        try:
            while self._active:
                data = stream.read(1024, exception_on_overflow=False)
                rms = math.sqrt(sum(x**2 for x in struct.unpack('1024h', data)) / 1024) / 32768.0
                if rms > self._threshold:
                    self._on_spike()
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()

    def _on_spike(self) -> None:
        now = time.time()
        if now - self._last_fire < self._cooldown_s:
            return
        if now - self._last_spike <= self._window_s:
            self._last_fire = now
            asyncio.create_task(self._fire())
        self._last_spike = now

    async def _fire(self) -> None:
        logger.info("ClapSystem: double-clap detected")
        for cb in self._callbacks:
            await cb()

    async def simulate_clap(self) -> None:
        """For testing only."""
        await self._fire()
