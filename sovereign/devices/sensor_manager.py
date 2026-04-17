"""Sensor manager — reads and aggregates data from physical/virtual sensors."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Awaitable, Any

logger = logging.getLogger(__name__)

SensorCallback = Callable[[str, Any], Awaitable[None]]


@dataclass
class SensorReading:
    sensor_id: str
    value: Any
    unit: str = ""
    timestamp: float = field(default_factory=time.time)
    quality: float = 1.0


@dataclass
class SensorSpec:
    sensor_id: str
    name: str
    unit: str
    poll_interval_s: float = 5.0
    reader: Callable[[], Any] | None = None


class SensorManager:
    """
    Polls registered sensors and notifies subscribers on new readings.
    Includes built-in readers: CPU usage, memory usage, battery level.
    """

    def __init__(self) -> None:
        self._sensors: dict[str, SensorSpec] = {}
        self._last_readings: dict[str, SensorReading] = {}
        self._callbacks: list[SensorCallback] = []
        self._running = False
        self._register_builtins()

    def _register_builtins(self) -> None:
        self._sensors["cpu_percent"] = SensorSpec(
            "cpu_percent", "CPU Usage", "%", 5.0, self._read_cpu
        )
        self._sensors["mem_percent"] = SensorSpec(
            "mem_percent", "Memory Usage", "%", 10.0, self._read_mem
        )
        self._sensors["battery"] = SensorSpec(
            "battery", "Battery Level", "%", 60.0, self._read_battery
        )

    def register(self, spec: SensorSpec) -> None:
        self._sensors[spec.sensor_id] = spec

    def subscribe(self, callback: SensorCallback) -> None:
        self._callbacks.append(callback)

    async def read(self, sensor_id: str) -> SensorReading | None:
        spec = self._sensors.get(sensor_id)
        if not spec or not spec.reader:
            return self._last_readings.get(sensor_id)
        try:
            value = spec.reader()
            reading = SensorReading(sensor_id=sensor_id, value=value, unit=spec.unit)
            self._last_readings[sensor_id] = reading
            return reading
        except Exception as exc:
            logger.warning("Sensor %s read error: %s", sensor_id, exc)
            return None

    async def run_loop(self, stop_event: asyncio.Event | None = None) -> None:
        self._running = True
        logger.info("SensorManager started")
        last_poll: dict[str, float] = {}
        while self._running:
            if stop_event and stop_event.is_set():
                break
            now = time.time()
            for sid, spec in self._sensors.items():
                if now - last_poll.get(sid, 0) >= spec.poll_interval_s:
                    reading = await self.read(sid)
                    if reading:
                        last_poll[sid] = now
                        for cb in self._callbacks:
                            try:
                                await cb(sid, reading.value)
                            except Exception as exc:
                                logger.warning("Sensor callback error: %s", exc)
            await asyncio.sleep(1.0)

    def stop(self) -> None:
        self._running = False

    def snapshot(self) -> dict[str, Any]:
        return {sid: r.value for sid, r in self._last_readings.items()}

    # ── Built-in readers ───────────────────────────────────────────────────

    def _read_cpu(self) -> float:
        try:
            import psutil  # type: ignore
            return psutil.cpu_percent(interval=0.1)
        except ImportError:
            return 0.0

    def _read_mem(self) -> float:
        try:
            import psutil  # type: ignore
            return psutil.virtual_memory().percent
        except ImportError:
            return 0.0

    def _read_battery(self) -> float | None:
        try:
            import psutil  # type: ignore
            bat = psutil.sensors_battery()
            return bat.percent if bat else None
        except (ImportError, AttributeError):
            return None
