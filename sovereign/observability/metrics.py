"""
Metrics system — structured metrics collection for SOVEREIGN AI OS.

Provides: counters, gauges, histograms, and time-series with in-memory
storage and periodic JSONL persistence. Replaces ad-hoc logging for
tracking system performance over time.
"""
from __future__ import annotations

import json
import logging
import pathlib
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_PATH = pathlib.Path("data/ledger/metrics.jsonl")


@dataclass
class MetricPoint:
    """A single metric data point."""
    metric_name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def iso_ts(self) -> str:
        return datetime.fromtimestamp(self.ts, tz=timezone.utc).isoformat()


class MetricsCollector:
    """
    In-memory metrics store with persistence.

    Metric types:
    - counter: monotonically increasing value (e.g., requests_total)
    - gauge: point-in-time value (e.g., active_sessions)
    - histogram: distribution of values (e.g., response_latency_ms)
    """

    def __init__(self, data_path: str | pathlib.Path = _DEFAULT_PATH) -> None:
        self._path = pathlib.Path(data_path)
        self._counters: dict[str, float] = defaultdict(float)
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._series: list[MetricPoint] = []  # time-series store
        self._flush_interval = 100  # flush every N points

    # ------------------------------------------------------------------
    # Counter
    # ------------------------------------------------------------------

    def inc(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """Increment a counter."""
        key = self._key(name, labels or {})
        self._counters[key] += value
        self._record(name, self._counters[key], labels or {})

    def counter_value(self, name: str, labels: dict[str, str] | None = None) -> float:
        return self._counters.get(self._key(name, labels or {}), 0.0)

    # ------------------------------------------------------------------
    # Gauge
    # ------------------------------------------------------------------

    def set(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Set a gauge to a specific value."""
        key = self._key(name, labels or {})
        self._gauges[key] = value
        self._record(name, value, labels or {})

    def gauge_value(self, name: str, labels: dict[str, str] | None = None) -> float:
        return self._gauges.get(self._key(name, labels or {}), 0.0)

    # ------------------------------------------------------------------
    # Histogram
    # ------------------------------------------------------------------

    def observe(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Record a histogram observation."""
        key = self._key(name, labels or {})
        self._histograms[key].append(value)
        self._record(name, value, labels or {})

    def histogram_summary(self, name: str, labels: dict[str, str] | None = None) -> dict[str, float]:
        """Return p50, p90, p99, mean, count for a histogram."""
        key = self._key(name, labels or {})
        data = sorted(self._histograms.get(key, []))
        if not data:
            return {}
        n = len(data)
        return {
            "count": n,
            "mean": round(sum(data) / n, 3),
            "min": data[0],
            "max": data[-1],
            "p50": data[int(n * 0.50)],
            "p90": data[int(n * 0.90)],
            "p99": data[int(n * 0.99)],
        }

    # ------------------------------------------------------------------
    # Time-series queries
    # ------------------------------------------------------------------

    def query(
        self,
        name: str,
        since: float | None = None,
        labels: dict[str, str] | None = None,
        limit: int = 100,
    ) -> list[MetricPoint]:
        """Query time-series points for a metric."""
        results = [p for p in self._series if p.metric_name == name]
        if since:
            results = [p for p in results if p.ts >= since]
        if labels:
            results = [
                p for p in results
                if all(p.labels.get(k) == v for k, v in labels.items())
            ]
        return results[-limit:]

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Current state of all metrics."""
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histogram_names": list(self._histograms.keys()),
            "series_points": len(self._series),
        }

    def agent_performance(self) -> dict[str, Any]:
        """Aggregate per-agent performance metrics."""
        agents: dict[str, dict] = {}
        for point in self._series:
            aid = point.labels.get("agent_id")
            if not aid:
                continue
            if aid not in agents:
                agents[aid] = {"calls": 0, "tokens": 0, "latency_ms": []}
            if point.metric_name == "agent_calls_total":
                agents[aid]["calls"] += 1
            elif point.metric_name == "agent_tokens_used":
                agents[aid]["tokens"] += point.value
            elif point.metric_name == "agent_latency_ms":
                agents[aid]["latency_ms"].append(point.value)

        result = {}
        for aid, data in agents.items():
            lats = sorted(data["latency_ms"])
            result[aid] = {
                "calls": data["calls"],
                "tokens": data["tokens"],
                "avg_latency_ms": round(sum(lats) / len(lats), 1) if lats else 0,
            }
        return result

    def flush(self) -> None:
        """Persist all recent series points to disk."""
        if not self._series:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as f:
                for point in self._series[-self._flush_interval:]:
                    f.write(json.dumps(asdict(point)) + "\n")
        except Exception as exc:
            logger.error("Metrics flush failed: %s", exc)

    # ------------------------------------------------------------------

    def _key(self, name: str, labels: dict[str, str]) -> str:
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def _record(self, name: str, value: float, labels: dict[str, str]) -> None:
        point = MetricPoint(metric_name=name, value=value, labels=labels)
        self._series.append(point)
        if len(self._series) % self._flush_interval == 0:
            self.flush()


# Convenience functions for common sovereign metrics
def record_agent_call(
    metrics: MetricsCollector,
    agent_id: str,
    latency_ms: float,
    tokens: int,
    success: bool,
) -> None:
    """Record a single agent call's metrics."""
    labels = {"agent_id": agent_id}
    metrics.inc("agent_calls_total", labels=labels)
    metrics.inc("agent_calls_success" if success else "agent_calls_failure", labels=labels)
    metrics.observe("agent_latency_ms", latency_ms, labels=labels)
    metrics.inc("agent_tokens_used", float(tokens), labels=labels)


def record_session(
    metrics: MetricsCollector,
    mode: str,
    latency_ms: float,
    tokens: int,
    tasks: int,
) -> None:
    """Record session-level metrics."""
    labels = {"mode": mode}
    metrics.inc("sessions_total", labels=labels)
    metrics.observe("session_latency_ms", latency_ms, labels=labels)
    metrics.inc("session_tokens_total", float(tokens), labels=labels)
    metrics.observe("session_tasks", float(tasks), labels=labels)
