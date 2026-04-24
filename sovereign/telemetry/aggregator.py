"""
Telemetry aggregator — computes summary statistics over stored sessions.
"""
from __future__ import annotations

import statistics
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from sovereign.telemetry.store import get_telemetry_store
from sovereign.telemetry.types import AggregatedStats


def _records_in_window(hours: int) -> list[dict]:
    store = get_telemetry_store()
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
    result = []
    for r in store.iter_all():
        try:
            ts_str = r.get("started_at", "")
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
