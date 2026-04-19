"""
Tests for infra/queue.py and proactive/forecast_engine.py.
"""
from __future__ import annotations

import asyncio
import time
import pytest


# ===========================================================================
# TaskQueue
# ===========================================================================

class TestTaskQueue:
    @pytest.fixture
    def queue(self):
        from sovereign.infra.queue import TaskQueue
        return TaskQueue()

    @pytest.mark.asyncio
    async def test_enqueue_returns_task(self, queue):
        task = await queue.enqueue("agent1", "Do something", {})
        assert task.agent_id == "agent1"
        assert task.objective == "Do something"
        assert task.task_id is not None

    @pytest.mark.asyncio
    async def test_size_after_enqueue(self, queue):
        await queue.enqueue("a", "obj", {})
        await queue.enqueue("b", "obj2", {})
        assert queue.size() == 2

    @pytest.mark.asyncio
    async def test_dequeue_nowait_empty(self, queue):
        result = await queue.dequeue_nowait()
        assert result is None

    @pytest.mark.asyncio
    async def test_dequeue_nowait_returns_task(self, queue):
        await queue.enqueue("agent", "task", {})
        task = await queue.dequeue_nowait()
        assert task is not None
        assert task.status == "processing"

    @pytest.mark.asyncio
    async def test_dequeue_returns_task(self, queue):
        await queue.enqueue("agent", "task", {})
        task = await queue.dequeue()
        assert task.agent_id == "agent"
        assert task.status == "processing"

    @pytest.mark.asyncio
    async def test_priority_ordering(self, queue):
        from sovereign.infra.queue import TaskPriority
        await queue.enqueue("low", "low obj", {}, priority=TaskPriority.LOW)
        await queue.enqueue("crit", "crit obj", {}, priority=TaskPriority.CRITICAL)
        first = await queue.dequeue_nowait()
        assert first.agent_id == "crit"

    @pytest.mark.asyncio
    async def test_stats(self, queue):
        await queue.enqueue("a", "obj", {})
        stats = queue.stats()
        assert "enqueued_total" in stats
        assert stats["enqueued_total"] == 1

    @pytest.mark.asyncio
    async def test_mark_failed_to_dlq(self, queue):
        await queue.enqueue("a", "obj", {})
        task_obj = await queue.dequeue_nowait()
        task_obj.attempts = 2  # max_attempts - 1
        queue.mark_failed(task_obj)
        queue.mark_failed(task_obj)
        assert queue.dead_letter_count() >= 1

    @pytest.mark.asyncio
    async def test_mark_failed_retry(self, queue):
        await queue.enqueue("a", "obj", {})
        task_obj = await queue.dequeue_nowait()
        queue.mark_failed(task_obj)
        assert task_obj.attempts == 1
        assert task_obj.status == "failed"

    @pytest.mark.asyncio
    async def test_purge_dead_letters(self, queue):
        await queue.enqueue("a", "obj", {})
        task_obj = await queue.dequeue_nowait()
        task_obj.attempts = 3
        queue.mark_failed(task_obj)
        count = queue.purge_dead_letters()
        assert count >= 1
        assert queue.dead_letter_count() == 0

    @pytest.mark.asyncio
    async def test_requeue_dead_letters(self, queue):
        await queue.enqueue("a", "obj", {})
        task_obj = await queue.dequeue_nowait()
        task_obj.attempts = 3
        queue.mark_failed(task_obj)
        requeued = await queue.requeue_dead_letters()
        assert requeued == 1
        assert queue.dead_letter_count() == 0
        assert queue.size() == 1

    @pytest.mark.asyncio
    async def test_clear(self, queue):
        await queue.enqueue("a", "1", {})
        await queue.enqueue("b", "2", {})
        count = queue.clear()
        assert count == 2
        assert queue.size() == 0

    @pytest.mark.asyncio
    async def test_drain_empty_immediately(self, queue):
        result = await queue.drain(timeout_s=1.0)
        assert result is True

    @pytest.mark.asyncio
    async def test_pending(self, queue):
        await queue.enqueue("a", "obj", {})
        pending = queue.pending()
        assert len(pending) == 1

    @pytest.mark.asyncio
    async def test_on_dead_letter_callback(self, queue):
        called_with = []

        async def dlq_callback(task):
            called_with.append(task.task_id)

        queue.on_dead_letter(dlq_callback)
        await queue.enqueue("a", "obj", {})
        task_dequeued = await queue.dequeue_nowait()
        task_dequeued.attempts = 3
        queue.mark_failed(task_dequeued)
        await asyncio.sleep(0.05)
        assert len(called_with) >= 1


# ===========================================================================
# ForecastEngine
# ===========================================================================

class TestForecastEngine:
    @pytest.fixture
    def engine(self):
        from sovereign.proactive.forecast_engine import ForecastEngine
        return ForecastEngine()

    def test_instantiation(self, engine):
        assert engine is not None

    @pytest.mark.asyncio
    async def test_evaluate_empty_snapshot(self, engine):
        alerts = await engine.evaluate({})
        assert isinstance(alerts, list)

    @pytest.mark.asyncio
    async def test_evaluate_negative_cashflow(self, engine):
        snap = {"financial": {"monthly_cashflow": -500}}
        alerts = await engine.evaluate(snap)
        ids = [a.alert_id for a in alerts]
        assert any("cashflow" in a for a in ids)

    @pytest.mark.asyncio
    async def test_evaluate_low_cashflow(self, engine):
        snap = {"financial": {"monthly_cashflow": 100}}
        alerts = await engine.evaluate(snap)
        assert any("low_cashflow" in a.alert_id or "cashflow" in a.alert_id for a in alerts)

    @pytest.mark.asyncio
    async def test_evaluate_blocked_projects(self, engine):
        snap = {"project": [{"name": "ProjectA", "status": "blocked"}]}
        alerts = await engine.evaluate(snap)
        assert any("blocked" in a.alert_id for a in alerts)

    @pytest.mark.asyncio
    async def test_active_alerts_empty(self, engine):
        alerts = engine.active_alerts()
        assert isinstance(alerts, list)

    @pytest.mark.asyncio
    async def test_active_alerts_after_evaluate(self, engine):
        snap = {"financial": {"monthly_cashflow": -100}}
        await engine.evaluate(snap)
        alerts = engine.active_alerts()
        assert len(alerts) >= 1

    @pytest.mark.asyncio
    async def test_dismiss_alert(self, engine):
        snap = {"financial": {"monthly_cashflow": -100}}
        await engine.evaluate(snap)
        alerts = engine.active_alerts()
        if alerts:
            ok = engine.dismiss(alerts[0].alert_id)
            assert ok is True

    @pytest.mark.asyncio
    async def test_dismiss_nonexistent(self, engine):
        ok = engine.dismiss("nonexistent-id")
        assert ok is False

    def test_forecast_alert_not_expired(self):
        from sovereign.proactive.forecast_engine import ForecastAlert
        alert = ForecastAlert(
            alert_id="a1", title="Test", description="d",
            probability=0.8, impact="high", horizon_days=30,
            source="bayesian", recommended_action="review",
            expires_at=time.time() + 3600,
        )
        assert not alert.is_expired

    def test_forecast_alert_expired(self):
        from sovereign.proactive.forecast_engine import ForecastAlert
        alert = ForecastAlert(
            alert_id="a2", title="Test", description="d",
            probability=0.8, impact="high", horizon_days=30,
            source="bayesian", recommended_action="review",
            expires_at=time.time() - 1,
        )
        assert alert.is_expired

    def test_forecast_alert_no_expiry(self):
        from sovereign.proactive.forecast_engine import ForecastAlert
        alert = ForecastAlert(
            alert_id="a3", title="Test", description="d",
            probability=0.8, impact="high", horizon_days=30,
            source="bayesian", recommended_action="review",
            expires_at=0,  # never
        )
        assert not alert.is_expired

    @pytest.mark.asyncio
    async def test_dedup_same_alert(self, engine):
        snap = {"financial": {"monthly_cashflow": -100}}
        alerts1 = await engine.evaluate(snap)
        alerts2 = await engine.evaluate(snap)
        # Same alert_id should not be emitted twice
        ids1 = {a.alert_id for a in alerts1}
        ids2 = {a.alert_id for a in alerts2}
        assert ids1.isdisjoint(ids2) or len(alerts2) == 0


# ===========================================================================
# TaskPriority
# ===========================================================================

class TestTaskPriority:
    def test_priority_ordering(self):
        from sovereign.infra.queue import TaskPriority
        assert TaskPriority.CRITICAL < TaskPriority.HIGH
        assert TaskPriority.HIGH < TaskPriority.NORMAL
        assert TaskPriority.NORMAL < TaskPriority.LOW
        assert TaskPriority.LOW < TaskPriority.BACKGROUND
