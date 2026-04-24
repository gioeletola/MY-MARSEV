"""Tests for sovereign/telemetry/ suite."""
from __future__ import annotations

import pathlib
import tempfile
import time


from sovereign.telemetry.types import (
    PhaseMetric, PhaseStatus, SessionTelemetry,
)
from sovereign.telemetry.store import TelemetryStore


# ---------------------------------------------------------------------------
# PhaseMetric
# ---------------------------------------------------------------------------

def test_phase_metric_finish():
    pm = PhaseMetric(phase_name="input_pipeline", started_at=time.time() - 0.1)
    pm.finish(PhaseStatus.COMPLETED)
    assert pm.status == PhaseStatus.COMPLETED
    assert pm.duration_ms > 0
    assert pm.ended_at > pm.started_at


def test_phase_metric_finish_failed():
    pm = PhaseMetric(phase_name="ceo_agent", started_at=time.time())
    pm.finish(PhaseStatus.FAILED)
    assert pm.status == PhaseStatus.FAILED


# ---------------------------------------------------------------------------
# SessionTelemetry
# ---------------------------------------------------------------------------

def test_session_telemetry_add_phase():
    session = SessionTelemetry(session_id="test-123")
    pm = PhaseMetric(
        phase_name="phase1",
        tokens_input=100,
        tokens_output=50,
        tokens_cached=80,
        agent_id="ceo_agent",
        model_id="claude-sonnet-4-6",
    )
    session.add_phase(pm)
    assert session.total_tokens_input == 100
    assert session.total_tokens_output == 50
    assert session.total_tokens_cached == 80
    assert "ceo_agent" in session.agents_invoked
    assert "claude-sonnet-4-6" in session.models_used


def test_session_telemetry_deduplicates_agents():
    session = SessionTelemetry(session_id="test-456")
    for _ in range(3):
        pm = PhaseMetric(phase_name="p", agent_id="worker_agent", model_id="claude-haiku-4-5-20251001")
        session.add_phase(pm)
    assert session.agents_invoked.count("worker_agent") == 1
    assert session.models_used.count("claude-haiku-4-5-20251001") == 1


def test_session_telemetry_finish():
    session = SessionTelemetry(session_id="s1")
    time.sleep(0.01)
    session.finish(success=True)
    assert session.success is True
    assert session.total_latency_ms > 0
    assert session.ended_at > session.started_at


def test_session_telemetry_finish_with_error():
    session = SessionTelemetry(session_id="s2")
    session.finish(success=False, error="Something went wrong")
    assert session.success is False
    assert session.error == "Something went wrong"


def test_session_telemetry_to_dict():
    session = SessionTelemetry(session_id="dict-test", mode="business")
    session.add_phase(PhaseMetric(
        phase_name="p1", tokens_input=200, tokens_cached=150,
        agent_id="a1", model_id="m1",
    ))
    session.finish()
    d = session.to_dict()
    assert d["session_id"] == "dict-test"
    assert d["mode"] == "business"
    assert d["total_tokens_input"] == 200
    assert 0 <= d["cache_hit_rate"] <= 1
    assert "started_at" in d


# ---------------------------------------------------------------------------
# TelemetryStore
# ---------------------------------------------------------------------------

def test_telemetry_store_record_and_recent():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = pathlib.Path(f.name)

    store = TelemetryStore(path=path, ring_size=10)
    for i in range(5):
        session = SessionTelemetry(session_id=f"s{i}")
        session.finish()
        store.record(session)

    recent = store.recent(5)
    assert len(recent) == 5
    assert recent[0]["session_id"] == "s0"

    path.unlink(missing_ok=True)


def test_telemetry_store_respects_ring_size():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = pathlib.Path(f.name)

    store = TelemetryStore(path=path, ring_size=3)
    for i in range(6):
        session = SessionTelemetry(session_id=f"s{i}")
        session.finish()
        store.record(session)

    recent = store.recent(10)
    assert len(recent) == 3  # Ring buffer capped at 3
    assert recent[-1]["session_id"] == "s5"

    path.unlink(missing_ok=True)


def test_telemetry_store_iter_all():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = pathlib.Path(f.name)

    store = TelemetryStore(path=path)
    for i in range(3):
        session = SessionTelemetry(session_id=f"iter{i}")
        session.finish()
        store.record(session)

    records = list(store.iter_all())
    assert len(records) == 3
    ids = {r["session_id"] for r in records}
    assert ids == {"iter0", "iter1", "iter2"}

    path.unlink(missing_ok=True)


def test_telemetry_store_empty_iter():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=True) as f:
        path = pathlib.Path(f.name)
    # File deleted — iter_all should yield nothing
    store = TelemetryStore(path=path)
    records = list(store.iter_all())
    assert records == []
