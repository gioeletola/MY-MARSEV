"""
Telemetry store — real-time, thread-safe ring buffer for TelemetryEvents.

Features:
- Thread-safe ring buffer (configurable max_events, default 10 000)
- record(event_type, source, data, tags) — stores TelemetryEvent with timestamp+uuid
- query(event_type, source, since_iso, until_iso, limit) — filtered query
- aggregate(event_type, window_seconds) — count/sum/mean for numeric fields
- flush() — clear events beyond retention window
- export_jsonl(path) — dump ring buffer to JSONL file
- stats() — summary dict
- Backward-compatible record(session: SessionTelemetry) for legacy callers
"""
from __future__ import annotations

import json
import logging
import pathlib
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any

from sovereign.telemetry.types import SessionTelemetry, TelemetryEvent

logger = logging.getLogger(__name__)

_DEFAULT_PATH = pathlib.Path("data/ledger/telemetry.jsonl")
_DEFAULT_MAX_EVENTS = 10_000
_DEFAULT_RETENTION_HOURS = 168  # 7 days


class TelemetryStore:
    """
    Real-time telemetry store backed by an in-memory ring buffer.

    Thread-safe for concurrent record/query from multiple threads.
    Optionally persists events to a JSONL file for durability.
    """

    def __init__(
        self,
        path: pathlib.Path = _DEFAULT_PATH,
        max_events: int = _DEFAULT_MAX_EVENTS,
        retention_hours: int = _DEFAULT_RETENTION_HOURS,
        persist: bool = True,
        # Alias kept for backward compat
        ring_size: int | None = None,
    ) -> None:
        self._path = path
        self._max_events = ring_size if ring_size is not None else max_events
        self._retention_hours = retention_hours
        self._persist = persist
        self._lock = threading.RLock()
        self._ring: deque[TelemetryEvent] = deque(maxlen=self._max_events)
        if persist:
            self._path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(
        self,
        event_type_or_session: "str | SessionTelemetry" = "custom",
        source: str = "system",
        data: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> TelemetryEvent | None:
        """
        Record a new telemetry event.

        Can be called two ways:
          store.record("request", "ceo_agent", {"latency_ms": 123}, ["prod"])
          store.record(session_telemetry_obj)  # legacy compat
        """
        # Legacy compatibility: accept a SessionTelemetry object
        if isinstance(event_type_or_session, SessionTelemetry):
            session = event_type_or_session
            raw = session.to_dict()
            event = TelemetryEvent(
                event_type="session_end",
                source=raw.get("mode", "session"),
                data=raw,
                tags=["session"],
            )
        else:
            event = TelemetryEvent(
                event_type=str(event_type_or_session),
                source=source,
                data=data or {},
                tags=tags or [],
            )

        with self._lock:
            self._ring.append(event)

        if self._persist:
            self._write_jsonl(event)

        return event

    def _write_jsonl(self, event: TelemetryEvent) -> None:
        try:
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event.to_dict()) + "\n")
        except OSError as exc:
            logger.warning("TelemetryStore: write failed: %s", exc)

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def query(
        self,
        event_type: str | None = None,
        source: str | None = None,
        since_iso: str | None = None,
        until_iso: str | None = None,
        limit: int = 100,
        tags: list[str] | None = None,
    ) -> list[TelemetryEvent]:
        """
        Filter events from the ring buffer.

        Args:
            event_type: exact match on event_type (None = all)
            source: exact match on source (None = all)
            since_iso: ISO timestamp — include events at or after this time
            until_iso: ISO timestamp — include events at or before this time
            limit: max results (most recent first)
            tags: all tags in this list must be present on the event

        Returns:
            List of matching TelemetryEvent objects (most recent first).
        """
        since_dt = _parse_iso(since_iso)
        until_dt = _parse_iso(until_iso)

        with self._lock:
            snapshot = list(self._ring)

        results: list[TelemetryEvent] = []
        for ev in reversed(snapshot):
            if event_type and ev.event_type != event_type:
                continue
            if source and ev.source != source:
                continue
            ev_dt = _parse_iso(ev.timestamp)
            if since_dt and ev_dt and ev_dt < since_dt:
                continue
            if until_dt and ev_dt and ev_dt > until_dt:
                continue
            if tags and not all(t in ev.tags for t in tags):
                continue
            results.append(ev)
            if len(results) >= limit:
                break

        return results

    def recent(self, n: int = 50) -> list[dict]:
        """Return the n most-recent raw dicts (legacy compat).

        Data fields are merged into the top-level dict so callers can access
        session-level keys (e.g. ``session_id``) directly.
        """
        with self._lock:
            snapshot = list(self._ring)
        out = []
        for ev in snapshot[-n:]:
            d = ev.to_dict()
            inner = d.pop("data", {}) or {}
            if isinstance(inner, dict):
                d.update(inner)
            else:
                d["data"] = inner
            out.append(d)
        return out

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    def aggregate(
        self,
        event_type: str,
        window_seconds: int = 3600,
    ) -> dict[str, Any]:
        """
        Compute count, sum, and mean for all numeric fields in matching events.

        Args:
            event_type: only include events of this type
            window_seconds: look-back window in seconds

        Returns:
            Dict with keys: count, numeric field stats {field: {count, sum, mean}}
        """
        since_dt = _utcnow_minus(window_seconds)
        events = self.query(
            event_type=event_type,
            since_iso=since_dt.isoformat(),
            limit=self._max_events,
        )

        if not events:
            return {"count": 0, "fields": {}}

        # Collect numeric values per field name
        field_values: dict[str, list[float]] = {}
        for ev in events:
            for k, v in ev.data.items():
                if isinstance(v, (int, float)):
                    field_values.setdefault(k, []).append(float(v))

        field_stats: dict[str, dict[str, float]] = {}
        for fname, vals in field_values.items():
            field_stats[fname] = {
                "count": len(vals),
                "sum": sum(vals),
                "mean": sum(vals) / len(vals) if vals else 0.0,
                "min": min(vals),
                "max": max(vals),
            }

        return {"count": len(events), "fields": field_stats}

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def flush(self, retention_hours: int | None = None) -> int:
        """
        Remove events older than retention_hours from the ring buffer.

        Returns the number of events removed.
        """
        hours = retention_hours if retention_hours is not None else self._retention_hours
        cutoff = _utcnow_minus(hours * 3600)
        removed = 0

        with self._lock:
            original = list(self._ring)
            kept: list[TelemetryEvent] = []
            for ev in original:
                ev_dt = _parse_iso(ev.timestamp)
                if ev_dt and ev_dt < cutoff:
                    removed += 1
                else:
                    kept.append(ev)
            self._ring.clear()
            self._ring.extend(kept)

        if removed:
            logger.debug("TelemetryStore.flush: removed %d old events", removed)
        return removed

    # ------------------------------------------------------------------
    # Export & Stats
    # ------------------------------------------------------------------

    def export_jsonl(self, path: str | pathlib.Path) -> int:
        """
        Dump all ring-buffer events to a JSONL file.

        Returns the number of events written.
        """
        dest = pathlib.Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        with self._lock:
            snapshot = list(self._ring)

        count = 0
        with dest.open("w", encoding="utf-8") as fh:
            for ev in snapshot:
                fh.write(json.dumps(ev.to_dict()) + "\n")
                count += 1

        logger.info("TelemetryStore.export_jsonl: wrote %d events to %s", count, dest)
        return count

    def stats(self) -> dict[str, Any]:
        """
        Return a summary dict:
          total_events, events_by_type, events_by_source,
          oldest_event_ts, newest_event_ts, ring_capacity
        """
        with self._lock:
            snapshot = list(self._ring)

        by_type: dict[str, int] = {}
        by_source: dict[str, int] = {}
        timestamps: list[str] = []

        for ev in snapshot:
            by_type[ev.event_type] = by_type.get(ev.event_type, 0) + 1
            by_source[ev.source] = by_source.get(ev.source, 0) + 1
            timestamps.append(ev.timestamp)

        timestamps_sorted = sorted(timestamps)
        return {
            "total_events": len(snapshot),
            "ring_capacity": self._max_events,
            "events_by_type": by_type,
            "events_by_source": by_source,
            "oldest_event_ts": timestamps_sorted[0] if timestamps_sorted else None,
            "newest_event_ts": timestamps_sorted[-1] if timestamps_sorted else None,
        }

    # ------------------------------------------------------------------
    # Legacy iterator (reads JSONL file on disk)
    # ------------------------------------------------------------------

    def iter_all(self):
        """Iterate over all persisted events from the JSONL file."""
        if not self._path.exists():
            return
        with self._path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    inner = d.pop("data", {}) or {}
                    if isinstance(inner, dict):
                        d.update(inner)
                    else:
                        d["data"] = inner
                    yield d
                except json.JSONDecodeError:
                    continue

    def count(self) -> int:
        with self._lock:
            return len(self._ring)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _utcnow_minus(seconds: int) -> datetime:
    from datetime import timedelta
    return datetime.now(timezone.utc) - timedelta(seconds=seconds)


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_store: TelemetryStore | None = None


def get_telemetry_store() -> TelemetryStore:
    global _store
    if _store is None:
        _store = TelemetryStore()
    return _store
