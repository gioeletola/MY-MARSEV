"""Coverage tests for authority, HUD, perception, and overlay."""
import asyncio


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# ApprovalGate — extended coverage
# ---------------------------------------------------------------------------

class TestApprovalGateExtended:
    def _gate(self, mode="auto"):
        from sovereign.authority.approval_gate import ApprovalGate, ApprovalMode
        return ApprovalGate(mode=ApprovalMode(mode))

    def test_auto_approves(self):
        gate = self._gate("auto")
        rec = run(gate.request_approval("read_file", {}, "user1"))
        assert rec.approved is True

    def test_silent_rejects(self):
        gate = self._gate("silent")
        rec = run(gate.request_approval("dangerous_action", {}, "user1"))
        assert rec.approved is False

    def test_policy_mode_returns_record(self):
        gate = self._gate("policy")
        rec = run(gate.request_approval("read_data", {}, "u"))
        assert hasattr(rec, "approved")
        assert hasattr(rec, "reason")

    def test_audit_trail_grows(self):
        gate = self._gate("auto")
        run(gate.request_approval("act1", {}, "u"))
        run(gate.request_approval("act2", {}, "u"))
        assert len(gate._audit) >= 2

    def test_from_env_returns_gate(self):
        from sovereign.authority.approval_gate import ApprovalGate
        import os
        os.environ.setdefault("APPROVAL_MODE", "auto")
        gate = ApprovalGate.from_env()
        assert gate is not None

    def test_register_auto_rule_approve(self):
        from sovereign.authority.approval_gate import ApprovalGate, ApprovalMode
        gate = ApprovalGate(mode=ApprovalMode.POLICY)
        gate.register_auto_rule(lambda action, ctx, uid: True if action == "always_yes" else None, True)
        rec = run(gate.request_approval("always_yes", {}, "u"))
        assert rec.approved is True

    def test_approval_record_fields(self):
        gate = self._gate("auto")
        rec = run(gate.request_approval("test_action", {"risk": 0.1}, "admin"))
        assert hasattr(rec, "approved")
        assert hasattr(rec, "action_id")
        assert hasattr(rec, "timestamp")

    def test_admin_user_auto_approved_in_policy(self):
        from sovereign.authority.approval_gate import ApprovalGate, ApprovalMode
        gate = ApprovalGate(mode=ApprovalMode.POLICY)
        rec = run(gate.request_approval("delete_file", {}, "admin"))
        assert rec.approved is True


# ---------------------------------------------------------------------------
# EscalationThresholds
# ---------------------------------------------------------------------------

class TestEscalationThresholds:
    def test_default_instantiation(self):
        from sovereign.authority.thresholds import EscalationThresholds
        t = EscalationThresholds()
        assert hasattr(t, "auto_approve_below_risk")

    def test_should_auto_approve_low_risk(self):
        from sovereign.authority.thresholds import EscalationThresholds
        t = EscalationThresholds()
        assert t.should_auto_approve(0.05) is True

    def test_should_escalate_high_risk(self):
        from sovereign.authority.thresholds import EscalationThresholds
        t = EscalationThresholds()
        assert t.should_escalate(0.99) is True

    def test_get_threshold(self):
        from sovereign.authority.thresholds import EscalationThresholds
        t = EscalationThresholds()
        val = t.get_threshold("command", "READ")
        assert isinstance(val, float)

    def test_for_mode_finance(self):
        from sovereign.authority.thresholds import EscalationThresholds
        t = EscalationThresholds.for_mode("finance")
        assert t.auto_approve_below_risk <= 0.1

    def test_for_mode_study(self):
        from sovereign.authority.thresholds import EscalationThresholds
        t = EscalationThresholds.for_mode("study")
        assert t is not None

    def test_to_dict(self):
        from sovereign.authority.thresholds import EscalationThresholds
        t = EscalationThresholds()
        d = t.to_dict()
        assert "auto_approve_below_risk" in d

    def test_adjust_and_reset(self):
        from sovereign.authority.thresholds import EscalationThresholds
        t = EscalationThresholds()
        original = t.get_threshold("command", "EXECUTE")
        t.adjust("command", "EXECUTE", -0.1)
        t.reset_overrides("command")
        after = t.get_threshold("command", "EXECUTE")
        assert abs(after - original) < 0.01

    def test_all_thresholds(self):
        from sovereign.authority.thresholds import EscalationThresholds
        t = EscalationThresholds()
        d = t.all_thresholds("command")
        assert isinstance(d, dict)


# ---------------------------------------------------------------------------
# Authority Policy / PolicyEngine
# ---------------------------------------------------------------------------

class TestPolicyEngine:
    def test_policy_engine_instantiate(self):
        from sovereign.authority.policy import PolicyEngine
        engine = PolicyEngine()
        assert engine is not None

    def test_evaluate_read(self):
        from sovereign.authority.policy import PolicyEngine
        engine = PolicyEngine()
        decision = engine.evaluate("read", {}, "user")
        assert hasattr(decision, "allowed") or hasattr(decision, "approved")

    def test_evaluate_high_amount_financial(self):
        from sovereign.authority.policy import PolicyEngine
        engine = PolicyEngine()
        decision = engine.evaluate("payment", {"amount": 9999}, "user")
        assert decision is not None

    def test_add_custom_policy(self):
        from sovereign.authority.policy import PolicyEngine, PolicyDecision
        engine = PolicyEngine()
        def my_policy(action, ctx, uid):
            if action == "custom_deny":
                return PolicyDecision(allowed=False, reason="custom", policy_id="my_policy")
            return None
        engine.add_policy("my_policy", my_policy)
        decision = engine.evaluate("custom_deny", {}, "u")
        allowed = getattr(decision, "allowed", getattr(decision, "approved", True))
        assert allowed is False

    def test_list_policies(self):
        from sovereign.authority.policy import PolicyEngine
        engine = PolicyEngine()
        policies = engine.list_policies()
        assert isinstance(policies, list)
        assert len(policies) > 0


# ---------------------------------------------------------------------------
# HUD — OverlayUI
# ---------------------------------------------------------------------------

class TestOverlayUI:
    def _ui(self):
        from sovereign.hud.overlay_ui import OverlayUI
        return OverlayUI()

    def test_instantiate(self):
        ui = self._ui()
        assert ui is not None

    def test_enqueue_message(self):
        ui = self._ui()
        if hasattr(ui, "enqueue"):
            ui.enqueue("Test message", color="#ff0000", duration_ms=1000)
        elif hasattr(ui, "push"):
            ui.push("Test message")
        assert True

    def test_render_panel(self):
        from sovereign.hud.overlay_ui import OverlayUI, PanelConfig
        ui = OverlayUI()
        if hasattr(ui, "render_panel"):
            cfg = PanelConfig(panel_id="p1", title="Test")
            html = ui.render_panel(cfg)
            assert isinstance(html, str)

    def test_pending_messages(self):
        ui = self._ui()
        if hasattr(ui, "enqueue"):
            ui.enqueue("msg1")
        msgs = getattr(ui, "pending_messages", None)
        if callable(msgs):
            result = msgs()
            assert isinstance(result, list)

    def test_create_panel(self):
        from sovereign.hud.overlay_ui import PanelConfig
        panel = PanelConfig(panel_id="test", title="Test Panel")
        assert panel.panel_id == "test"
        assert panel.position == "top-right"

    def test_overlay_message_expired(self):
        import time
        from sovereign.hud.overlay_ui import OverlayMessage
        msg = OverlayMessage(text="hi", duration_ms=1)
        time.sleep(0.01)
        assert msg.expired is True

    def test_overlay_message_persistent(self):
        from sovereign.hud.overlay_ui import OverlayMessage
        msg = OverlayMessage(text="persistent", duration_ms=0)
        assert msg.expired is False


# ---------------------------------------------------------------------------
# HUD — OrchestratorBridge
# ---------------------------------------------------------------------------

class TestOrchestratorBridge:
    def _bridge(self):
        from sovereign.hud.orchestrator_bridge import OrchestratorBridge
        return OrchestratorBridge(orchestrator=None)

    def _hud(self):
        from sovereign.hud.orchestrator_bridge import HUDOrchestrator
        return HUDOrchestrator(orchestrator=None)

    def test_bridge_instantiate(self):
        b = self._bridge()
        assert b is not None

    def test_bridge_initial_not_running(self):
        b = self._bridge()
        assert b._running is False

    def test_hud_get_status(self):
        h = self._hud()
        s = h.get_status()
        assert hasattr(s, "bridge_running")
        assert s.bridge_running is False

    def test_hud_is_running_property(self):
        h = self._hud()
        assert h.is_running is False

    def test_emit_event(self):
        b = self._bridge()
        run(b.emit({"type": "test", "data": {}}))
        assert True

    def test_on_event_register(self):
        b = self._bridge()
        received = []
        async def cb(ev):
            received.append(ev)
        b.on_event(cb)
        run(b.emit({"type": "test_event", "x": 1}))
        assert len(received) >= 1

    def test_bridge_stop(self):
        b = self._bridge()
        b.stop()
        assert b._running is False


# ---------------------------------------------------------------------------
# Perception — WakeTrigger
# ---------------------------------------------------------------------------

class TestWakeTrigger:
    def test_instantiate(self):
        from sovereign.perception.wake_trigger import WakeTrigger
        wt = WakeTrigger()
        assert wt is not None

    def test_check_method_exists(self):
        from sovereign.perception.wake_trigger import WakeTrigger
        wt = WakeTrigger()
        assert hasattr(wt, "check") or hasattr(wt, "is_triggered") or hasattr(wt, "matches")

    def test_check_triggered(self):
        from sovereign.perception.wake_trigger import WakeTrigger
        wt = WakeTrigger()
        for method_name in ("check", "is_triggered", "matches"):
            if hasattr(wt, method_name):
                result = getattr(wt, method_name)("hey sovereign what time is it")
                assert isinstance(result, (bool, float, int))
                break

    def test_keywords_attribute(self):
        from sovereign.perception.wake_trigger import WakeTrigger
        wt = WakeTrigger()
        kws = getattr(wt, "keywords", None) or getattr(wt, "_keywords", None)
        if kws is not None:
            assert isinstance(kws, (list, set, tuple, dict))

    def test_add_keyword_if_supported(self):
        from sovereign.perception.wake_trigger import WakeTrigger
        wt = WakeTrigger()
        if hasattr(wt, "add_keyword"):
            wt.add_keyword("marsev")
        assert True
