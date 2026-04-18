"""Tests for EvalAgent and MetricsCollector."""
from __future__ import annotations
import pytest

from sovereign.observability.eval_agent import EvalAgent
from sovereign.observability.metrics import MetricsCollector, record_agent_call


@pytest.fixture
def eval_agent(tmp_path):
    return EvalAgent(data_path=tmp_path / "evals.jsonl")


@pytest.fixture
def metrics(tmp_path):
    return MetricsCollector(data_path=tmp_path / "metrics.jsonl")


# ── EvalAgent ────────────────────────────────────────────────────────────────

def test_good_output_passes(eval_agent):
    good_output = (
        "## Analysis\n\n"
        "- Step 1: Review the current cashflow statement and identify gaps.\n"
        "- Step 2: Recommend immediate action to reduce discretionary spending.\n"
        "- Step 3: Schedule a review meeting with the finance team.\n\n"
        "**Next steps:** Implement the budget changes within 7 days. "
        "Priority items should be addressed first. Complete the review by end of week."
    )
    result = eval_agent.evaluate("s1", "cashflow_analyst", "t1", "Analyse cashflow", good_output)
    assert result.passed is True
    assert result.overall >= 0.60


def test_short_output_fails(eval_agent):
    result = eval_agent.evaluate("s1", "test_agent", "t1", "Do something", "Too short.")
    assert result.passed is False


def test_safety_violation_fails(eval_agent):
    result = eval_agent.evaluate("s1", "test_agent", "t1", "Help", "Here is your api_key: abc123secret")
    assert result.safety == 0.0
    assert result.passed is False


def test_overall_score_in_range(eval_agent):
    result = eval_agent.evaluate("s1", "agent", "t1", "objective", "Some result text here.")
    assert 0.0 <= result.overall <= 1.0


def test_agent_stats_after_eval(eval_agent):
    eval_agent.evaluate("s1", "target_agent", "t1", "obj", "short")
    stats = eval_agent.agent_stats("target_agent")
    assert "evals" in stats
    assert stats["evals"] == 1


def test_failing_agents_returns_list(eval_agent):
    eval_agent.evaluate("s1", "bad_agent", "t1", "obj", "bad")
    failing = eval_agent.failing_agents()
    assert isinstance(failing, list)


def test_overall_stats(eval_agent):
    eval_agent.evaluate("s1", "a1", "t1", "obj", "Some decent output with recommendations and next steps.")
    stats = eval_agent.overall_stats()
    assert "total" in stats
    assert stats["total"] >= 1


# ── MetricsCollector ─────────────────────────────────────────────────────────

def test_counter_increments(metrics):
    metrics.inc("test_counter")
    metrics.inc("test_counter")
    assert metrics.counter_value("test_counter") == 2.0


def test_counter_with_value(metrics):
    metrics.inc("tokens", 100.0)
    assert metrics.counter_value("tokens") == 100.0


def test_gauge_set(metrics):
    metrics.set("active_sessions", 5.0)
    assert metrics.gauge_value("active_sessions") == 5.0


def test_gauge_overwrite(metrics):
    metrics.set("g1", 1.0)
    metrics.set("g1", 99.0)
    assert metrics.gauge_value("g1") == 99.0


def test_histogram_observe(metrics):
    metrics.observe("latency_ms", 100.0)
    summary = metrics.histogram_summary("latency_ms")
    assert summary["count"] == 1
    assert summary["mean"] == 100.0


def test_histogram_multiple_observations(metrics):
    for v in [10, 20, 30, 40, 50]:
        metrics.observe("resp_time", float(v))
    summary = metrics.histogram_summary("resp_time")
    assert summary["count"] == 5
    assert summary["min"] == 10.0
    assert summary["max"] == 50.0


def test_record_agent_call(metrics):
    record_agent_call(metrics, "test_agent", latency_ms=150.0, tokens=500, success=True)
    assert metrics.counter_value("agent_calls_total", {"agent_id": "test_agent"}) >= 1


def test_snapshot_returns_dict(metrics):
    metrics.inc("x")
    snap = metrics.snapshot()
    assert isinstance(snap, dict)
    assert "counters" in snap


def test_query_time_series(metrics):
    import time
    t0 = time.time()
    metrics.inc("events")
    points = metrics.query("events", since=t0 - 1)
    assert len(points) >= 1


def test_missing_gauge_returns_zero(metrics):
    assert metrics.gauge_value("nonexistent_gauge") == 0.0


def test_missing_counter_returns_zero(metrics):
    assert metrics.counter_value("nonexistent_counter") == 0.0
