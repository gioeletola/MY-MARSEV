"""
Tests for sovereign/security/ modules:
  access_control, session_monitor, lockdown, quarantine.
Also covers routing_rules and agent_scaffolder.
"""
from __future__ import annotations

import pytest


# ===========================================================================
# AccessControl
# ===========================================================================

class TestAccessControl:
    @pytest.fixture
    def ac(self, tmp_path):
        from sovereign.security.access_control import AccessControlLayer
        return AccessControlLayer(policy_path=tmp_path / "policies.json")

    def _make_policy(self, resource="files", allowed_roles=None, deny_agents=None):
        from sovereign.security.access_control import AccessPolicy
        return AccessPolicy(
            policy_id=f"pol-{resource}",
            resource=resource,
            allowed_roles=allowed_roles or ["admin"],
            allowed_agents=[],
            deny_agents=deny_agents or [],
        )

    def test_register_and_list(self, ac):
        ac.register_policy(self._make_policy("files"))
        policies = ac.list_policies()
        assert len(policies) >= 1

    def test_allow_by_role(self, ac):
        ac.register_policy(self._make_policy("files", allowed_roles=["admin"]))
        decision = ac.check(
            requester_id="agent-1", resource="files",
            action="read", context={"role": "admin"},
        )
        assert decision.allowed is True

    def test_deny_unknown_role(self, ac):
        ac.register_policy(self._make_policy("files", allowed_roles=["admin"]))
        decision = ac.check(
            requester_id="agent-1", resource="files",
            action="read", context={"role": "viewer"},
        )
        assert decision.allowed is False

    def test_deny_explicit_deny_agent(self, ac):
        ac.register_policy(self._make_policy("files", deny_agents=["bad_agent"]))
        decision = ac.check(
            requester_id="bad_agent", resource="files",
            action="write", context={"role": "admin"},
        )
        assert decision.allowed is False

    def test_no_policy_default_deny(self, ac):
        decision = ac.check(
            requester_id="a", resource="unknown_resource",
            action="read", context={},
        )
        assert decision.allowed is False

    def test_audit_log(self, ac):
        ac.register_policy(self._make_policy("files"))
        ac.check("agent-1", "files", "read", {"role": "admin"})
        log = ac.audit_log()
        assert isinstance(log, list)

    def test_allowed_agent_explicit(self, ac):
        from sovereign.security.access_control import AccessPolicy
        policy = AccessPolicy(
            policy_id="pol-a",
            resource="api",
            allowed_roles=[],
            allowed_agents=["trusted_agent"],
        )
        ac.register_policy(policy)
        d = ac.check("trusted_agent", "api", "call", {})
        assert d.allowed is True

    def test_persistence(self, tmp_path):
        from sovereign.security.access_control import AccessControlLayer
        path = tmp_path / "p.json"
        ac1 = AccessControlLayer(policy_path=path)
        ac1.register_policy(self._make_policy("vault"))
        ac2 = AccessControlLayer(policy_path=path)
        assert len(ac2.list_policies()) >= 1


# ===========================================================================
# SessionMonitor
# ===========================================================================

class TestSessionMonitor:
    @pytest.fixture
    def monitor(self, tmp_path):
        from sovereign.security.session_monitor import SessionMonitor
        return SessionMonitor(ledger_path=tmp_path / "sessions.jsonl")

    def test_record_event(self, monitor):
        monitor.record("session-001", "agent-001", "task_start", {"task": "research"})
        events = monitor.get_session("session-001")
        assert len(events) >= 1

    def test_get_session_empty(self, monitor):
        events = monitor.get_session("nonexistent")
        assert events == []

    def test_active_sessions(self, monitor):
        monitor.record("sess-1", "a-001", "start", {})
        monitor.record("sess-2", "a-002", "start", {})
        active = monitor.active_sessions()
        assert "sess-1" in active
        assert "sess-2" in active

    def test_close_session(self, monitor):
        monitor.record("sess-1", "a-001", "start", {})
        monitor.close_session("sess-1")
        active = monitor.active_sessions()
        assert "sess-1" not in active

    def test_anomalies_empty(self, monitor):
        assert monitor.anomalies() == []

    def test_rate_spike_anomaly(self, monitor):
        for i in range(25):
            monitor.record("sess-spike", f"agent-{i}", "event", {})
        anomalies = monitor.anomalies()
        assert len(anomalies) >= 1

    def test_persistence(self, tmp_path):
        from sovereign.security.session_monitor import SessionMonitor
        path = tmp_path / "s.jsonl"
        m1 = SessionMonitor(ledger_path=path)
        m1.record("sess-p", "agent-p", "action", {})
        m2 = SessionMonitor(ledger_path=path)
        events = m2.get_session("sess-p")
        assert len(events) >= 1


# ===========================================================================
# Lockdown
# ===========================================================================

class TestLockdown:
    @pytest.fixture
    def lockdown(self, tmp_path):
        from sovereign.security.lockdown import LockdownManager
        return LockdownManager(store_path=tmp_path / "lockdown.json")

    def test_inactive_initially(self, lockdown):
        from sovereign.security.lockdown import LockdownLevel
        assert lockdown.current_level() == LockdownLevel.NORMAL

    def test_activate_elevated(self, lockdown):
        from sovereign.security.lockdown import LockdownLevel
        lockdown.activate(LockdownLevel.ELEVATED, reason="test", activated_by="admin")
        assert lockdown.current_level() == LockdownLevel.ELEVATED

    def test_elevated_allows_execute(self, lockdown):
        from sovereign.security.lockdown import LockdownLevel
        lockdown.activate(LockdownLevel.ELEVATED, reason="test", activated_by="admin")
        assert lockdown.is_action_allowed("READ") is True
        assert lockdown.is_action_allowed("EXECUTE") is True

    def test_critical_blocks_execute(self, lockdown):
        from sovereign.security.lockdown import LockdownLevel
        lockdown.activate(LockdownLevel.CRITICAL, reason="breach", activated_by="admin")
        assert lockdown.is_action_allowed("READ") is True
        assert lockdown.is_action_allowed("EXECUTE") is False

    def test_deactivate(self, lockdown):
        from sovereign.security.lockdown import LockdownLevel
        lockdown.activate(LockdownLevel.ELEVATED, reason="test", activated_by="admin")
        lockdown.deactivate(deactivated_by="admin")
        assert lockdown.current_level() == LockdownLevel.NORMAL

    def test_status(self, lockdown):
        s = lockdown.status()
        assert "level" in s

    def test_persistence(self, tmp_path):
        from sovereign.security.lockdown import LockdownManager, LockdownLevel
        path = tmp_path / "lock.json"
        l1 = LockdownManager(store_path=path)
        l1.activate(LockdownLevel.HIGH, reason="test", activated_by="admin")
        l2 = LockdownManager(store_path=path)
        assert l2.current_level() == LockdownLevel.HIGH

    def test_normal_allows_all(self, lockdown):
        assert lockdown.is_action_allowed("READ") is True
        assert lockdown.is_action_allowed("EXECUTE") is True


# ===========================================================================
# Quarantine
# ===========================================================================

class TestQuarantine:
    @pytest.fixture
    def quarantine(self, tmp_path):
        from sovereign.security.quarantine import QuarantineManager
        return QuarantineManager(store_path=tmp_path / "quarantine.json")

    def test_quarantine_agent(self, quarantine):
        quarantine.quarantine("agent-bad", reason="repeated failures", quarantined_by="guardian")
        assert quarantine.is_quarantined("agent-bad") is True

    def test_not_quarantined_by_default(self, quarantine):
        assert quarantine.is_quarantined("agent-good") is False

    def test_release_agent(self, quarantine):
        quarantine.quarantine("agent-x", reason="test", quarantined_by="system")
        ok = quarantine.release("agent-x", released_by="admin")
        assert ok is True
        assert quarantine.is_quarantined("agent-x") is False

    def test_release_nonexistent(self, quarantine):
        ok = quarantine.release("ghost", released_by="admin")
        assert ok is False

    def test_quarantined_agents_list(self, quarantine):
        quarantine.quarantine("a-1", reason="r1", quarantined_by="s")
        quarantine.quarantine("a-2", reason="r2", quarantined_by="s")
        agents = quarantine.quarantined_agents()
        ids = [r.agent_id for r in agents]
        assert "a-1" in ids and "a-2" in ids

    def test_check_and_quarantine_threshold(self, quarantine):
        for _ in range(5):
            quarantine.check_and_quarantine("agent-flaky", failure_count=5, threshold=3)
        assert quarantine.is_quarantined("agent-flaky") is True

    def test_persistence(self, tmp_path):
        from sovereign.security.quarantine import QuarantineManager
        path = tmp_path / "q.json"
        q1 = QuarantineManager(store_path=path)
        q1.quarantine("agent-persist", reason="persist test", quarantined_by="admin")
        q2 = QuarantineManager(store_path=path)
        assert q2.is_quarantined("agent-persist") is True


# ===========================================================================
# Routing rules
# ===========================================================================

class TestRoutingRules:
    def test_load_nonexistent_returns_empty(self):
        from sovereign.router.routing_rules import load_routing_rules
        rules = load_routing_rules("nonexistent_file.yaml")
        assert rules == []

    def test_apply_rules_no_rules(self):
        from sovereign.router.routing_rules import apply_rules
        result = apply_rules([], {"complexity": 0.9})
        assert result == "balanced"

    def test_apply_rules_match_above(self):
        from sovereign.router.routing_rules import apply_rules
        # The full condition key must match the context key exactly
        rules = [{"if": {"task_complexity_above": 0.8}, "use": "frontier"}]
        result = apply_rules(rules, {"task_complexity_above": 0.9})
        assert result == "frontier"

    def test_apply_rules_no_match_default(self):
        from sovereign.router.routing_rules import apply_rules
        rules = [{"if": {"task_complexity_above": 0.9}, "use": "frontier"}]
        result = apply_rules(rules, {"task_complexity_above": 0.5}, default="balanced")
        assert result == "balanced"

    def test_apply_rules_below_condition(self):
        from sovereign.router.routing_rules import apply_rules
        rules = [{"if": {"latency_budget_ms_below": 1000}, "use": "fast"}]
        result = apply_rules(rules, {"latency_budget_ms_below": 500})
        assert result == "fast"

    def test_apply_rules_exact_match(self):
        from sovereign.router.routing_rules import apply_rules
        rules = [{"if": {"mode": "command"}, "use": "frontier"}]
        result = apply_rules(rules, {"mode": "command"})
        assert result == "frontier"

    def test_apply_rules_missing_context_key(self):
        from sovereign.router.routing_rules import apply_rules
        rules = [{"if": {"missing_key": True}, "use": "frontier"}]
        result = apply_rules(rules, {})
        assert result == "balanced"


# ===========================================================================
# AgentScaffolder
# ===========================================================================

class TestAgentScaffolder:
    @pytest.fixture
    def scaffolder(self, tmp_path):
        from sovereign.expansion.agent_scaffolder import AgentScaffolder
        return AgentScaffolder(output_dir=str(tmp_path / "generated"))

    def _make_bp(self, agent_id="test_agent"):
        from sovereign.expansion.agent_scaffolder import AgentBlueprint
        return AgentBlueprint(
            agent_id=agent_id,
            specialty="Data Analyst",
            instructions="Analyze data and provide insights.",
            tools=["code_exec", "memory_tool"],
        )

    def test_generate_code(self, scaffolder):
        bp = self._make_bp()
        code = scaffolder.generate_code(bp)
        assert "test_agent" in code
        assert "Data Analyst" in code
        assert "class DataAnalystAgent" in code

    def test_scaffold_writes_file(self, scaffolder, tmp_path):
        bp = self._make_bp("my_agent")
        scaffolder.scaffold(bp, write=True)
        files = list((tmp_path / "generated").glob("*.py"))
        assert len(files) >= 1

    def test_scaffold_no_write(self, scaffolder):
        bp = self._make_bp()
        code = scaffolder.scaffold(bp, write=False)
        assert "DataAnalystAgent" in code

    def test_scaffold_many(self, scaffolder):
        from sovereign.expansion.agent_scaffolder import AgentBlueprint
        bps = [
            AgentBlueprint(agent_id=f"agent-{i}", specialty=f"Spec {i}", instructions=f"inst {i}")
            for i in range(3)
        ]
        codes = scaffolder.scaffold_many(bps)
        assert len(codes) == 3

    def test_code_has_system_prompt(self, scaffolder):
        bp = self._make_bp()
        code = scaffolder.generate_code(bp)
        assert "SYSTEM_PROMPT" in code
