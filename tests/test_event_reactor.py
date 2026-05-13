"""Tests for ProactiveEventReactor."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from sovereign.events.event_bus import EventBus
from sovereign.events.event_types import EventType, SovereignEvent
from sovereign.proactive.event_reactor import ProactiveEventReactor


def _mock_orch():
    orch = MagicMock()
    orch._memory = MagicMock()
    orch._memory.write = AsyncMock()
    return orch


class TestProactiveEventReactor:
    def test_attach_registers_five_hooks(self):
        bus = EventBus()
        reactor = ProactiveEventReactor(_mock_orch())
        reactor.attach(bus)
        total = sum(
            bus.subscriber_count(et)
            for et in (
                EventType.APPROVAL_REQUIRED,
                EventType.SECURITY_ALERT,
                EventType.TASK_FAILED,
                EventType.HEALTH_UPDATE,
                EventType.JOB_COMPLETE,
            )
        )
        assert total == 5

    def test_detach_removes_all_hooks(self):
        bus = EventBus()
        reactor = ProactiveEventReactor(_mock_orch())
        reactor.attach(bus)
        reactor.detach(bus)
        for et in (EventType.APPROVAL_REQUIRED, EventType.SECURITY_ALERT,
                   EventType.TASK_FAILED, EventType.HEALTH_UPDATE, EventType.JOB_COMPLETE):
            assert bus.subscriber_count(et) == 0

    @pytest.mark.asyncio
    async def test_approval_required_sends_telegram(self):
        reactor = ProactiveEventReactor(_mock_orch())
        reactor._tg_token = "tok"
        reactor._tg_chat = "123"
        with patch.object(reactor, "_telegram", new_callable=AsyncMock) as mock_tg:
            await reactor._on_approval_required(SovereignEvent(
                type=EventType.APPROVAL_REQUIRED,
                data={"task_id": "t1", "agent_id": "guardian", "action": "EXECUTE"},
            ))
        mock_tg.assert_awaited_once()
        msg = mock_tg.call_args[0][0]
        assert "guardian" in msg
        assert "t1" in msg

    @pytest.mark.asyncio
    async def test_security_alert_writes_memory(self):
        orch = _mock_orch()
        reactor = ProactiveEventReactor(orch)
        with patch.object(reactor, "_telegram", new_callable=AsyncMock):
            await reactor._on_security_alert(SovereignEvent(
                type=EventType.SECURITY_ALERT,
                data={"severity": "CRITICAL", "detail": "Injection attempt"},
            ))
        orch._memory.write.assert_awaited_once()
        args = orch._memory.write.call_args[0]
        assert args[0] == "operational"

    @pytest.mark.asyncio
    async def test_task_failed_critical_agent_notifies(self):
        reactor = ProactiveEventReactor(_mock_orch())
        with patch.object(reactor, "_telegram", new_callable=AsyncMock) as mock_tg:
            with patch.object(reactor, "_memory_write", new_callable=AsyncMock):
                await reactor._on_task_failed(SovereignEvent(
                    type=EventType.TASK_FAILED,
                    data={"task_id": "t2", "agent_id": "ceo", "error": "timeout"},
                ))
        mock_tg.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_task_failed_non_critical_agent_no_telegram(self):
        reactor = ProactiveEventReactor(_mock_orch())
        with patch.object(reactor, "_telegram", new_callable=AsyncMock) as mock_tg:
            with patch.object(reactor, "_memory_write", new_callable=AsyncMock):
                await reactor._on_task_failed(SovereignEvent(
                    type=EventType.TASK_FAILED,
                    data={"task_id": "t3", "agent_id": "expense_tracker", "error": "err"},
                ))
        mock_tg.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_health_update_degraded_notifies(self):
        reactor = ProactiveEventReactor(_mock_orch())
        with patch.object(reactor, "_telegram", new_callable=AsyncMock) as mock_tg:
            await reactor._on_health_update(SovereignEvent(
                type=EventType.HEALTH_UPDATE,
                data={"overall": "degraded", "alerts": ["Memory usage high"]},
            ))
        mock_tg.assert_awaited_once()
        assert "DEGRADED" in mock_tg.call_args[0][0]

    @pytest.mark.asyncio
    async def test_health_update_healthy_no_telegram(self):
        reactor = ProactiveEventReactor(_mock_orch())
        with patch.object(reactor, "_telegram", new_callable=AsyncMock) as mock_tg:
            await reactor._on_health_update(SovereignEvent(
                type=EventType.HEALTH_UPDATE,
                data={"overall": "healthy"},
            ))
        mock_tg.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_job_complete_writes_memory(self):
        orch = _mock_orch()
        reactor = ProactiveEventReactor(orch)
        await reactor._on_job_complete(SovereignEvent(
            type=EventType.JOB_COMPLETE,
            data={"job_id": "j1", "name": "daily_health_check"},
        ))
        orch._memory.write.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_telegram_skipped_when_not_configured(self):
        reactor = ProactiveEventReactor(_mock_orch())
        reactor._tg_token = ""
        reactor._tg_chat = ""
        # Should not raise; just silently skip
        await reactor._telegram("test message")

    def test_end_to_end_via_event_bus(self):
        """Emit via bus → reactor handler is scheduled (sync path check)."""
        bus = EventBus()
        orch = _mock_orch()
        reactor = ProactiveEventReactor(orch)
        reactor.attach(bus)
        fired = []

        original = reactor._on_job_complete

        async def _spy(event):
            fired.append(event.type)
            await original(event)

        reactor._on_job_complete = _spy
        bus.unsubscribe(EventType.JOB_COMPLETE, original)
        bus.subscribe(EventType.JOB_COMPLETE, _spy)

        import asyncio
        asyncio.run(bus.emit_async(SovereignEvent(
            type=EventType.JOB_COMPLETE,
            data={"job_id": "jx", "name": "test"},
        )))
        assert EventType.JOB_COMPLETE in fired
