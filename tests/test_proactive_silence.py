"""Tests for AdaptiveSilence (proactive/adaptive_silence.py)."""
from __future__ import annotations

import asyncio
import time
import pytest


class TestFocusLevel:
    def test_all_levels_exist(self):
        from sovereign.proactive.adaptive_silence import FocusLevel
        levels = {fl.value for fl in FocusLevel}
        assert "idle" in levels
        assert "available" in levels
        assert "soft" in levels
        assert "deep" in levels
        assert "locked" in levels


class TestAdaptiveSilence:
    @pytest.fixture
    def silence(self):
        from sovereign.proactive.adaptive_silence import AdaptiveSilence
        return AdaptiveSilence()

    def test_initial_level_available(self, silence):
        from sovereign.proactive.adaptive_silence import FocusLevel
        assert silence.current_level == FocusLevel.AVAILABLE

    def test_record_activity(self, silence):
        before = time.time()
        silence.record_activity()
        assert silence._last_activity >= before

    def test_record_absence(self, silence):
        before = time.time()
        silence.record_absence()
        assert silence._last_absence >= before

    def test_set_manual_override(self, silence):
        from sovereign.proactive.adaptive_silence import FocusLevel
        silence.set_manual(FocusLevel.DEEP)
        assert silence.current_level == FocusLevel.DEEP

    def test_clear_manual(self, silence):
        from sovereign.proactive.adaptive_silence import FocusLevel
        silence.set_manual(FocusLevel.DEEP)
        silence.clear_manual()
        assert silence._manual_override is None

    def test_should_interrupt_available(self, silence):
        from sovereign.proactive.adaptive_silence import FocusLevel
        silence._level = FocusLevel.AVAILABLE
        assert silence.should_interrupt(0.1) is True
        assert silence.should_interrupt(1.0) is True

    def test_should_interrupt_idle(self, silence):
        from sovereign.proactive.adaptive_silence import FocusLevel
        silence._level = FocusLevel.IDLE
        assert silence.should_interrupt(0.99) is False

    def test_should_interrupt_locked(self, silence):
        from sovereign.proactive.adaptive_silence import FocusLevel
        silence._level = FocusLevel.LOCKED
        assert silence.should_interrupt(0.9) is False
        assert silence.should_interrupt(1.0) is True

    def test_should_interrupt_deep(self, silence):
        from sovereign.proactive.adaptive_silence import FocusLevel
        silence._level = FocusLevel.DEEP
        assert silence.should_interrupt(0.5) is False
        assert silence.should_interrupt(0.95) is True

    def test_should_interrupt_soft(self, silence):
        from sovereign.proactive.adaptive_silence import FocusLevel
        silence._level = FocusLevel.SOFT
        assert silence.should_interrupt(0.3) is False
        assert silence.should_interrupt(0.7) is True

    def test_on_level_change_callback(self, silence):
        from sovereign.proactive.adaptive_silence import FocusLevel
        received = []
        silence.on_level_change(lambda lvl: received.append(lvl))
        silence.set_manual(FocusLevel.DEEP)
        assert len(received) == 1
        assert received[0] == FocusLevel.DEEP

    def test_evaluate_idle_on_long_inactivity(self, silence):
        from sovereign.proactive.adaptive_silence import FocusLevel, SilenceConfig
        from sovereign.proactive.adaptive_silence import AdaptiveSilence
        cfg = SilenceConfig(idle_threshold_s=3.0, soft_focus_inactivity_s=0.5)
        s = AdaptiveSilence(config=cfg)
        s._last_activity = time.time() - 5.0  # 5s ago → idle
        s._evaluate()
        assert s.current_level == FocusLevel.IDLE

    def test_evaluate_soft_on_medium_inactivity(self, silence):
        from sovereign.proactive.adaptive_silence import FocusLevel, SilenceConfig
        from sovereign.proactive.adaptive_silence import AdaptiveSilence
        cfg = SilenceConfig(idle_threshold_s=10.0, soft_focus_inactivity_s=2.0)
        s = AdaptiveSilence(config=cfg)
        s._last_activity = time.time() - 5.0  # 5s ago, between soft_focus(2s) and idle(10s)
        s._evaluate()
        assert s.current_level == FocusLevel.SOFT

    def test_history_records_transitions(self, silence):
        from sovereign.proactive.adaptive_silence import FocusLevel
        silence.set_manual(FocusLevel.DEEP)
        silence.set_manual(FocusLevel.AVAILABLE)
        assert len(silence._history) >= 2

    def test_summary(self, silence):
        s = silence.summary()
        assert "level" in s
        assert "since_last_activity_s" in s
        assert "history_count" in s

    def test_stop(self, silence):
        silence._running = True
        silence.stop()
        assert silence._running is False

    def test_manual_override_expires(self, silence):
        from sovereign.proactive.adaptive_silence import FocusLevel
        silence.set_manual(FocusLevel.LOCKED, duration_s=0.001)
        time.sleep(0.01)
        # Force expiry via _evaluate
        silence._last_activity = time.time() - 0.001
        silence._evaluate()
        assert silence._manual_override is None

    def test_callback_with_error_doesnt_crash(self, silence):
        from sovereign.proactive.adaptive_silence import FocusLevel

        def bad_callback(lvl):
            raise RuntimeError("oops")

        silence.on_level_change(bad_callback)
        silence.set_manual(FocusLevel.DEEP)  # Should not raise

    @pytest.mark.asyncio
    async def test_run_loop_stops_on_event(self, silence):
        stop = asyncio.Event()
        stop.set()
        # Should return immediately
        task = asyncio.create_task(silence.run_loop(stop_event=stop))
        await asyncio.wait_for(task, timeout=1.0)
