"""
Telemetry store — persists SessionTelemetry records as JSONL.
Thread-safe append-only writes; in-memory ring buffer for recent sessions.
"""
from __future__ import annotations

import json
import logging
import pathlib
import threading
from collections import deque
from typing import Iterator

from sovereign.telemetry.types import SessionTelemetry

logger = logging.getLogger(__name__)

_DEFAULT_PATH = pathlib.Path("data/ledger/telemetry.jsonl")
_RING_SIZE = 500


class TelemetryStore:
    def __init__(self, path: pathlib.Path = _DEFAULT_PATH, ring_size: int = _RING_SIZE) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._ring: deque[dict] = deque(maxlen=ring_size)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, session: SessionTelemetry) -> None:
        record = session.to_dict()
        with self._lock:
            self._ring.append(record)
            try:
                with self._path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(record) + "\n")
            except OSError as exc:
                logger.warning("TelemetryStore: write failed: %s", exc)

    def recent(self, n: int = 50) -> list[dict]:
        with self._lock:
            items = list(self._ring)
        return items[-n:]

    def iter_all(self) -> Iterator[dict]:
        if not self._path.exists():
            return
        with self._path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    def count(self) -> int:
        with self._lock:
            return len(self._ring)


_store: TelemetryStore | None = None


def get_telemetry_store() -> TelemetryStore:
    global _store
    if _store is None:
        _store = TelemetryStore()
    return _store
