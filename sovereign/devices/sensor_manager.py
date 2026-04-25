"""Sensor manager — reads and aggregates data from physical/virtual sensors."""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

SensorCallback = Callable[[str, Any], Awaitable[None]]

_HISTORY_MAXLEN = 100


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
    Includes built-in readers: CPU usage, memory usage, disk usage,
    battery level, and network byte counters (all via psutil with graceful
    fallback if psutil is not installed).
    """

    def __init__(self) -> None:
        self._sensors: dict[str, SensorSpec] = {}
        self._last_readings: dict[str, SensorReading] = {}
        self._history: dict[str, deque] = {}
        self._callbacks: list[SensorCallback] = []
        self._running = False
        self._register_builtins()

    def _register_builtins(self) -> None:
        builtins = [
            SensorSpec("cpu_percent", "CPU Usage", "%", 5.0, self._read_cpu),
            SensorSpec("memory_percent", "Memory Usage", "%", 10.0, self._read_mem),
            SensorSpec("disk_percent", "Disk Usage", "%", 30.0, self._read_disk),
            SensorSpec("battery_percent", "Battery Level", "%", 60.0, self._read_battery),
            SensorSpec(
                "network_bytes_sent", "Network Bytes Sent", "bytes", 10.0,
                self._read_net_sent,
            ),
            SensorSpec(
                "network_bytes_recv", "Network Bytes Recv", "bytes", 10.0,
                self._read_net_recv,
            ),
        ]
        for spec in builtins:
            self._sensors[spec.sensor_id] = spec
            self._history[spec.sensor_id] = deque(maxlen=_HISTORY_MAXLEN)

        # Legacy alias kept for backwards compatibility
        self._sensors["mem_percent"] = self._sensors["memory_percent"]

    def register(self, spec: SensorSpec) -> None:
        self._sensors[spec.sensor_id] = spec
        if spec.sensor_id not in self._history:
            self._history[spec.sensor_id] = deque(maxlen=_HISTORY_MAXLEN)

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
            hist = self._history.setdefault(sensor_id, deque(maxlen=_HISTORY_MAXLEN))
            hist.append(reading)
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
            for sid, spec in list(self._sensors.items()):
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

    def get_latest(self, sensor_id: str) -> SensorReading | None:
        """Return the most recent SensorReading for *sensor_id*, or None."""
        return self._last_readings.get(sensor_id)

    def get_history(self, sensor_id: str, n: int = 10) -> list[SensorReading]:
        """Return the last *n* readings for *sensor_id* (oldest first)."""
        hist = self._history.get(sensor_id)
        if not hist:
            return []
        items = list(hist)
        return items[-n:] if n < len(items) else items

    def snapshot(self) -> dict[str, Any]:
        """Return a dict of all latest sensor values keyed by sensor_id."""
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

    def _read_disk(self) -> float:
        try:
            import psutil  # type: ignore
            return psutil.disk_usage("/").percent
        except ImportError:
            return 0.0

    def _read_battery(self) -> float | None:
        try:
            import psutil  # type: ignore
            bat = psutil.sensors_battery()
            return bat.percent if bat else None
        except (ImportError, AttributeError):
            return None

    def _read_net_sent(self) -> int:
        try:
            import psutil  # type: ignore
            return psutil.net_io_counters().bytes_sent
        except (ImportError, AttributeError):
            return 0

    def _read_net_recv(self) -> int:
        try:
            import psutil  # type: ignore
            return psutil.net_io_counters().bytes_recv
        except (ImportError, AttributeError):
            return 0
