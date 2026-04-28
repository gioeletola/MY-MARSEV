"""Sensor manager — reads and aggregates data from physical/virtual sensors."""
from __future__ import annotations

import asyncio
import logging
import math
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
    quality_score: float = 1.0
    # Legacy alias
    quality: float = field(init=False)

    def __post_init__(self) -> None:
        self.quality = self.quality_score


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
    Includes built-in readers: CPU, memory, disk, battery, network (via psutil).

    New features:
    - ``read_all()`` — read every registered sensor at once.
    - Per-sensor subscriptions via ``subscribe(sensor_id, callback)``.
    - ``aggregate(sensor_id, window_seconds)`` — min/max/mean/std over a time window.
    """

    def __init__(self) -> None:
        self._sensors: dict[str, SensorSpec] = {}
        self._last_readings: dict[str, SensorReading] = {}
        self._history: dict[str, deque] = {}
        # Global callbacks (notified on every reading)
        self._global_callbacks: list[SensorCallback] = []
        # Per-sensor callbacks
        self._sensor_callbacks: dict[str, list[SensorCallback]] = {}
        self._running = False
        self._register_builtins()

    def _register_builtins(self) -> None:
        builtins = [
            SensorSpec("cpu_percent", "CPU Usage", "%", 5.0, self._read_cpu),
            SensorSpec("memory_percent", "Memory Usage", "%", 10.0, self._read_mem),
            SensorSpec("disk_percent", "Disk Usage", "%", 30.0, self._read_disk),
            SensorSpec("battery_percent", "Battery Level", "%", 60.0, self._read_battery),
            SensorSpec("network_bytes_sent", "Network Bytes Sent", "bytes", 10.0, self._read_net_sent),
            SensorSpec("network_bytes_recv", "Network Bytes Recv", "bytes", 10.0, self._read_net_recv),
        ]
        for spec in builtins:
            self._sensors[spec.sensor_id] = spec
            self._history[spec.sensor_id] = deque(maxlen=_HISTORY_MAXLEN)
        # Legacy alias
        self._sensors["mem_percent"] = self._sensors["memory_percent"]

    def register(self, spec: SensorSpec) -> None:
        self._sensors[spec.sensor_id] = spec
        if spec.sensor_id not in self._history:
            self._history[spec.sensor_id] = deque(maxlen=_HISTORY_MAXLEN)

    # ── Subscription ──────────────────────────────────────────────────────

    def subscribe(
        self,
        sensor_id_or_callback: Any,
        callback: SensorCallback | None = None,
    ) -> None:
        """Subscribe to sensor updates.

        Two calling conventions:
          subscribe(callback)                    → global (all sensors)
          subscribe(sensor_id: str, callback)    → per-sensor
        """
        if callable(sensor_id_or_callback) and callback is None:
            # Global subscription
            self._global_callbacks.append(sensor_id_or_callback)
        elif isinstance(sensor_id_or_callback, str) and callable(callback):
            sensor_id = sensor_id_or_callback
            self._sensor_callbacks.setdefault(sensor_id, []).append(callback)
        else:
            raise TypeError("subscribe(callback) or subscribe(sensor_id, callback)")

    # ── Reading ───────────────────────────────────────────────────────────

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

    async def read_all(self) -> list[SensorReading]:
        """Read every registered sensor and return all readings."""
        results: list[SensorReading] = []
        for sensor_id in list(self._sensors.keys()):
            reading = await self.read(sensor_id)
            if reading is not None:
                results.append(reading)
        return results

    # ── Aggregation ───────────────────────────────────────────────────────

    def aggregate(self, sensor_id: str, window_seconds: float) -> dict:
        """Compute min/max/mean/std for numeric readings within the last *window_seconds*."""
        hist = self._history.get(sensor_id)
        if not hist:
            return {"sensor_id": sensor_id, "count": 0, "min": None, "max": None, "mean": None, "std": None}

        cutoff = time.time() - window_seconds
        values: list[float] = []
        for r in hist:
            if r.timestamp >= cutoff:
                try:
                    values.append(float(r.value))
                except (TypeError, ValueError):
                    pass

        if not values:
            return {"sensor_id": sensor_id, "count": 0, "min": None, "max": None, "mean": None, "std": None}

        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std = math.sqrt(variance)

        return {
            "sensor_id": sensor_id,
            "window_seconds": window_seconds,
            "count": len(values),
            "min": round(min(values), 4),
            "max": round(max(values), 4),
            "mean": round(mean, 4),
            "std": round(std, 4),
        }

    # ── Main loop ─────────────────────────────────────────────────────────

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
                        # Global callbacks
                        for cb in self._global_callbacks:
                            try:
                                await cb(sid, reading.value)
                            except Exception as exc:
                                logger.warning("Sensor global callback error: %s", exc)
                        # Per-sensor callbacks
                        for cb in self._sensor_callbacks.get(sid, []):
                            try:
                                await cb(sid, reading.value)
                            except Exception as exc:
                                logger.warning("Sensor [%s] callback error: %s", sid, exc)
            await asyncio.sleep(1.0)

    def stop(self) -> None:
        self._running = False

    def get_latest(self, sensor_id: str) -> SensorReading | None:
        return self._last_readings.get(sensor_id)

    def get_history(self, sensor_id: str, n: int = 10) -> list[SensorReading]:
        hist = self._history.get(sensor_id)
        if not hist:
            return []
        items = list(hist)
        return items[-n:] if n < len(items) else items

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
