"""
Telemetry aggregator — computes real-time metrics and trends over the store.

Metrics computed:
  request_rate    — requests per minute in the window
  avg_latency_ms  — mean latency across request/session events
  error_rate      — fraction of events that are errors
  cache_hit_rate  — fraction of token-usage events with cache hits
  token_throughput — total tokens (input+output) per minute

Usage:
    agg = TelemetryAggregator()
    metrics = agg.compute_metrics(store, window_seconds=3600)
    trend_data = agg.trend(store, "avg_latency_ms", window_seconds=3600, buckets=10)
    is_alert = agg.alert_if(store, "error_rate", threshold=0.1, comparator="gt")
"""
from __future__ import annotations

import math
import statistics
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from sovereign.telemetry.store import TelemetryStore, _parse_iso, get_telemetry_store
from sovereign.telemetry.types import AggregatedStats


# ---------------------------------------------------------------------------
# Main aggregator class
# ---------------------------------------------------------------------------

class TelemetryAggregator:
    """Computes real-time metrics and trend data over a TelemetryStore."""

    def compute_metrics(
        self,
        store: TelemetryStore | None = None,
        window_seconds: int = 3600,
    ) -> dict[str, Any]:
        """
        Compute key operational metrics over the last window_seconds.

        Returns:
            Dict with request_rate, avg_latency_ms, error_rate,
            cache_hit_rate, token_throughput, event_count, window_seconds
        """
        s = store or get_telemetry_store()
        since = (datetime.now(timezone.utc) - timedelta(seconds=window_seconds)).isoformat()

        # Fetch all events in the window (high limit)
        all_events = s.query(since_iso=since, limit=50_000)

        if not all_events:
            return _empty_metrics(window_seconds)

        total = len(all_events)
        minutes = max(window_seconds / 60.0, 1.0)

        # request_rate
        request_events = [e for e in all_events if e.event_type in (
            "request", "session_start", "session_end", "agent_call"
        )]
        request_rate = len(request_events) / minutes

        # avg_latency_ms
        latencies: list[float] = []
        for ev in all_events:
            lat = ev.data.get("latency_ms") or ev.data.get("total_latency_ms")
            if lat is not None:
                try:
                    latencies.append(float(lat))
                except (ValueError, TypeError):
                    pass
        avg_latency_ms = statistics.mean(latencies) if latencies else 0.0

        # error_rate
        error_count = sum(1 for e in all_events if e.event_type == "error"
                          or e.data.get("success") is False)
        error_rate = error_count / total if total else 0.0

        # cache_hit_rate
        cache_hits = sum(1 for e in all_events if e.event_type == "cache_hit")
        cache_misses = sum(1 for e in all_events if e.event_type == "cache_miss")
        # Also compute from token_usage data fields
        total_input = 0
        total_cached = 0
        for ev in all_events:
            total_input += int(ev.data.get("total_tokens_input", 0))
            total_cached += int(ev.data.get("total_tokens_cached", 0))
        if total_input > 0:
            cache_hit_rate = total_cached / total_input
        elif (cache_hits + cache_misses) > 0:
            cache_hit_rate = cache_hits / (cache_hits + cache_misses)
        else:
            cache_hit_rate = 0.0

        # token_throughput (tokens per minute)
        total_output = sum(int(ev.data.get("total_tokens_output", 0)) for ev in all_events)
        token_throughput = (total_input + total_output) / minutes

        # p95 latency
        p95_latency_ms = 0.0
        if latencies:
            sorted_lat = sorted(latencies)
            idx = max(0, int(len(sorted_lat) * 0.95) - 1)
            p95_latency_ms = sorted_lat[idx]

        return {
            "window_seconds": window_seconds,
            "event_count": total,
            "request_rate": round(request_rate, 4),
            "avg_latency_ms": round(avg_latency_ms, 1),
            "p95_latency_ms": round(p95_latency_ms, 1),
            "error_rate": round(error_rate, 4),
            "cache_hit_rate": round(cache_hit_rate, 4),
            "token_throughput": round(token_throughput, 1),
            "total_tokens_input": total_input,
            "total_tokens_output": total_output,
            "total_tokens_cached": total_cached,
        }

    def trend(
        self,
        store: TelemetryStore | None = None,
        metric: str = "avg_latency_ms",
        window_seconds: int = 3600,
        buckets: int = 10,
    ) -> list[tuple[str, float]]:
        """
        Compute a time-series trend for a metric over the window.

        The window is divided into `buckets` equal sub-windows.
        For each bucket, compute_metrics is called and the metric value extracted.

        Returns:
            List of (iso_timestamp, value) tuples, oldest first.
        """
        s = store or get_telemetry_store()
        bucket_duration = window_seconds // max(buckets, 1)
        now = datetime.now(timezone.utc)
        result: list[tuple[str, float]] = []

        for i in range(buckets):
            bucket_end = now - timedelta(seconds=bucket_duration * (buckets - 1 - i))
            bucket_start = bucket_end - timedelta(seconds=bucket_duration)
            bucket_ts = bucket_start.isoformat()

            events = s.query(
                since_iso=bucket_start.isoformat(),
                until_iso=bucket_end.isoformat(),
                limit=10_000,
            )

            if not events:
                result.append((bucket_ts, 0.0))
                continue

            value = _extract_metric(metric, events, bucket_duration)
            result.append((bucket_ts, round(value, 4)))

        return result

    def alert_if(
        self,
        store: TelemetryStore | None = None,
        metric: str = "error_rate",
        threshold: float = 0.1,
        comparator: str = "gt",
        window_seconds: int = 3600,
    ) -> bool:
        """
        Evaluate whether a metric breaches a threshold.

        Args:
            metric: one of the keys returned by compute_metrics
            threshold: the value to compare against
            comparator: "gt" (>), "lt" (<), "gte" (>=), "lte" (<=), "eq" (==)
            window_seconds: look-back window

        Returns:
            True if the alert condition is met.
        """
        metrics = self.compute_metrics(store, window_seconds)
        value = metrics.get(metric, 0.0)
        ops = {
            "gt":  value > threshold,
            "lt":  value < threshold,
            "gte": value >= threshold,
            "lte": value <= threshold,
            "eq":  math.isclose(value, threshold, rel_tol=1e-6),
        }
        return ops.get(comparator, False)


# ---------------------------------------------------------------------------
# Legacy function API (backwards compat)
# ---------------------------------------------------------------------------

def _records_in_window(hours: int) -> list[dict]:
    store = get_telemetry_store()
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
    result = []
    for r in store.iter_all():
        try:
            ts_str = r.get("started_at", "") or r.get("timestamp", "")
            if not ts_str:
                continue
            ts = datetime.fromisoformat(ts_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                result.append(r)
        except (ValueError, TypeError):
            continue
    return result


def compute_stats(period: str = "day") -> AggregatedStats:
    hours_map = {"hour": 1, "day": 24, "week": 168}
    hours = hours_map.get(period, 24)
    records = _records_in_window(hours)

    if not records:
        return AggregatedStats(period=period)

    latencies = [r.get("total_latency_ms", 0.0) for r in records]
    latencies_sorted = sorted(latencies)
    p95_idx = max(0, int(len(latencies_sorted) * 0.95) - 1)

    agent_counter: Counter = Counter()
    model_counter: Counter = Counter()
    for r in records:
        for a in r.get("agents_invoked", []):
            agent_counter[a] += 1
        for m in r.get("models_used", []):
            model_counter[m] += 1

    cache_rates = [r.get("cache_hit_rate", 0.0) for r in records]

    return AggregatedStats(
        period=period,
        sessions_total=len(records),
        sessions_success=sum(1 for r in records if r.get("success")),
        sessions_failed=sum(1 for r in records if not r.get("success")),
        avg_latency_ms=statistics.mean(latencies) if latencies else 0.0,
        p95_latency_ms=latencies_sorted[p95_idx] if latencies_sorted else 0.0,
        total_tokens_input=sum(r.get("total_tokens_input", 0) for r in records),
        total_tokens_output=sum(r.get("total_tokens_output", 0) for r in records),
        total_tokens_cached=sum(r.get("total_tokens_cached", 0) for r in records),
        avg_cache_hit_rate=statistics.mean(cache_rates) if cache_rates else 0.0,
        top_agents=agent_counter.most_common(10),
        top_models=model_counter.most_common(5),
        approvals_triggered=sum(1 for r in records if r.get("approval_required")),
    )


def to_dict(stats: AggregatedStats) -> dict[str, Any]:
    return {
        "period": stats.period,
        "sessions_total": stats.sessions_total,
        "sessions_success": stats.sessions_success,
        "sessions_failed": stats.sessions_failed,
        "success_rate": (
            stats.sessions_success / max(stats.sessions_total, 1)
        ),
        "avg_latency_ms": round(stats.avg_latency_ms, 1),
        "p95_latency_ms": round(stats.p95_latency_ms, 1),
        "total_tokens_input": stats.total_tokens_input,
        "total_tokens_output": stats.total_tokens_output,
        "total_tokens_cached": stats.total_tokens_cached,
        "avg_cache_hit_rate": round(stats.avg_cache_hit_rate, 3),
        "top_agents": stats.top_agents,
        "top_models": stats.top_models,
        "approvals_triggered": stats.approvals_triggered,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _empty_metrics(window_seconds: int) -> dict[str, Any]:
    return {
        "window_seconds": window_seconds,
        "event_count": 0,
        "request_rate": 0.0,
        "avg_latency_ms": 0.0,
        "p95_latency_ms": 0.0,
        "error_rate": 0.0,
        "cache_hit_rate": 0.0,
        "token_throughput": 0.0,
        "total_tokens_input": 0,
        "total_tokens_output": 0,
        "total_tokens_cached": 0,
    }


def _extract_metric(metric: str, events: list, bucket_duration: int) -> float:
    """Extract a single metric value from a list of events for a bucket."""
    if not events:
        return 0.0

    minutes = max(bucket_duration / 60.0, 1.0)

    if metric == "request_rate":
        req_events = [e for e in events if e.event_type in (
            "request", "session_start", "session_end", "agent_call"
        )]
        return len(req_events) / minutes

    elif metric == "avg_latency_ms":
        lats = []
        for ev in events:
            lat = ev.data.get("latency_ms") or ev.data.get("total_latency_ms")
            if lat is not None:
                try:
                    lats.append(float(lat))
                except (ValueError, TypeError):
                    pass
        return statistics.mean(lats) if lats else 0.0

    elif metric == "error_rate":
        total = len(events)
        errors = sum(1 for e in events if e.event_type == "error"
                     or e.data.get("success") is False)
        return errors / total if total else 0.0

    elif metric == "cache_hit_rate":
        total_input = sum(int(ev.data.get("total_tokens_input", 0)) for ev in events)
        total_cached = sum(int(ev.data.get("total_tokens_cached", 0)) for ev in events)
        if total_input > 0:
            return total_cached / total_input
        hits = sum(1 for e in events if e.event_type == "cache_hit")
        misses = sum(1 for e in events if e.event_type == "cache_miss")
        denom = hits + misses
        return hits / denom if denom else 0.0

    elif metric == "token_throughput":
        total_in = sum(int(ev.data.get("total_tokens_input", 0)) for ev in events)
        total_out = sum(int(ev.data.get("total_tokens_output", 0)) for ev in events)
        return (total_in + total_out) / minutes

    else:
        # Generic: try to pull numeric field from event data
        vals = []
        for ev in events:
            v = ev.data.get(metric)
            if v is not None:
                try:
                    vals.append(float(v))
                except (ValueError, TypeError):
                    pass
        return statistics.mean(vals) if vals else 0.0
