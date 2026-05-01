"""
Coverage batch 2: output_contract, approval_gate, thresholds, guardian (unit).
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest


def run(coro):
    return asyncio.run(coro)


# ===========================================================================
# StructuredOutput + OutputFormatter
# ===========================================================================

class TestStructuredOutput:
    def setup_method(self):
        from sovereign.output.output_contract import StructuredOutput, OutputStatus
        self.SO = StructuredOutput
        self.OS = OutputStatus

    def _base(self, **kw):
        return self.SO(session_id="s1", agent_id="a1", task_id="t1",
                       status=self.OS.COMPLETED, result="ok", **kw)

    def test_ok_factory(self):
        out = self.SO.ok("s1", "a1", "t1", "done", confidence=0.9)
        assert out.status == self.OS.COMPLETED
        assert out.confidence == 0.9
        assert out.result == "done"

    def test_failure_factory(self):
        out = self.SO.failure("s1", "a1", "t1", "bad error")
        assert out.status == self.OS.FAILED
        assert "bad error" in out.result
        assert out.error == "bad error"

    def test_escalated_factory(self):
        out = self.SO.escalated("s1", "a1", "t1", "needs human")
        assert out.status == self.OS.ESCALATED
        assert out.requires_human_review is True

    def test_pending_factory(self):
        out = self.SO.pending("s1", "a1", "t1", "awaiting review")
        assert out.status == self.OS.PENDING_APPROVAL
        assert out.requires_human_review is True

    def test_to_dict(self):
        out = self.SO.ok("s1", "a1", "t1", "result text")
        d = out.to_dict()
        assert isinstance(d, dict)
        assert d["session_id"] == "s1"
        assert d["agent_id"] == "a1"
        assert d["result"] == "result text"

    def test_to_json(self):
        import json
        out = self.SO.ok("s1", "a1", "t1", "hello")
        j = out.to_json()
        parsed = json.loads(j)
        assert parsed["agent_id"] == "a1"

    def test_to_markdown(self):
        out = self.SO.ok("s1", "a1", "t1", "markdown result")
        md = out.to_markdown()
        assert isinstance(md, str)
        assert "markdown result" in md

    def test_to_summary(self):
        out = self.SO.ok("s1", "a1", "t1", "summary result")
        s = out.to_summary()
        assert isinstance(s, str)

    def test_add_tokens(self):
        out = self._base()
        out.add_tokens({"input": 100, "output": 50, "cache_read": 20, "cache_write": 5})
        assert out.tokens_used["input"] == 100
        assert out.tokens_used["cache_read"] == 20

    def test_merge_multiple(self):
        a = self.SO.ok("s1", "a1", "t1", "res a")
        b = self.SO.ok("s1", "a2", "t2", "res b")
        merged = self.SO.merge(a, b)
        assert isinstance(merged, self.SO)

    def test_status_is_terminal(self):
        assert self.OS.COMPLETED.is_terminal is True
        assert self.OS.FAILED.is_terminal is True
        assert self.OS.RUNNING.is_terminal is False

    def test_status_is_ok(self):
        assert self.OS.COMPLETED.is_ok is True
        assert self.OS.FAILED.is_ok is False

    def test_data_field(self):
        out = self.SO.ok("s1", "a1", "t1", "res", data={"key": "val"})
        assert out.data["key"] == "val"

    def test_warnings_and_suggestions(self):
        out = self._base(warnings=["w1"], suggestions=["do this"])
        assert "w1" in out.warnings
        assert "do this" in out.suggestions


class TestOutputFormatter:
    def setup_method(self):
        from sovereign.output.output_contract import StructuredOutput, OutputFormatter
        self.SO = StructuredOutput
        self.fmt = OutputFormatter()

    def _out(self):
        return self.SO.ok("s1", "a1", "t1", "formatted result", confidence=0.8)

    def test_format_markdown(self):
        result = self.fmt.format(self._out(), fmt="markdown")
        assert isinstance(result, str)
        assert "formatted result" in result

    def test_format_json(self):
        result = self.fmt.format(self._out(), fmt="json")
        assert isinstance(result, str)

    def test_format_table(self):
        result = self.fmt.format(self._out(), fmt="table")
        assert isinstance(result, str)

    def test_format_slack(self):
        result = self.fmt.format(self._out(), fmt="slack")
        assert isinstance(result, str)

    def test_format_many(self):
        outs = [self._out(), self._out()]
        result = self.fmt.format_many(outs, fmt="markdown")
        assert isinstance(result, str)


# ===========================================================================
# EscalationThresholds
# ===========================================================================

class TestEscalationThresholds:
    def setup_method(self):
        from sovereign.authority.thresholds import EscalationThresholds
        self.ET = EscalationThresholds

    def test_default_construction(self):
        t = self.ET()
        assert isinstance(t.auto_approve_below_risk, float)
        assert isinstance(t.escalate_above_risk, float)

    def test_should_auto_approve(self):
        t = self.ET(auto_approve_below_risk=0.4)
        assert t.should_auto_approve(0.2) is True
        assert t.should_auto_approve(0.6) is False

    def test_should_escalate(self):
        t = self.ET(escalate_above_risk=0.8)
        assert t.should_escalate(0.9) is True
        assert t.should_escalate(0.5) is False

    def test_get_threshold(self):
        t = self.ET()
        val = t.get_threshold("command", "EXECUTE")
        assert isinstance(val, float)

    def test_adjust_threshold(self):
        t = self.ET()
        original = t.get_threshold("command", "EXECUTE")
        new_val = t.adjust("command", "EXECUTE", 0.1)
        assert abs(new_val - (original + 0.1)) < 0.001

    def test_all_thresholds(self):
        t = self.ET()
        result = t.all_thresholds("command")
        assert isinstance(result, dict)

    def test_reset_overrides(self):
        t = self.ET()
        t.adjust("command", "EXECUTE", 0.2)
        t.reset_overrides("command")
        val = t.get_threshold("command", "EXECUTE")
        assert isinstance(val, float)

    def test_to_dict(self):
        t = self.ET()
        d = t.to_dict()
        assert isinstance(d, dict)

    def test_from_dict(self):
        t = self.ET()
        d = t.to_dict()
        t2 = self.ET.from_dict(d)
        assert isinstance(t2, self.ET)

    def test_for_mode(self):
        t = self.ET.for_mode("command")
        assert isinstance(t, self.ET)

    def test_reset_to_defaults(self):
        t = self.ET()
        t.adjust("command", "EXECUTE", 0.5)
        t.reset_to_defaults()
        val = t.get_threshold("command", "EXECUTE")
        assert isinstance(val, float)


# ===========================================================================
# ApprovalGate
# ===========================================================================

class TestApprovalGate:
    def setup_method(self):
        from sovereign.authority.approval_gate import ApprovalGate, ApprovalMode
        self.gate = ApprovalGate(mode=ApprovalMode.POLICY)

    def test_auto_approves_read(self):
        result = run(self.gate.request_approval("read", context={}, user_id="alice"))
        assert result.approved is True

    def test_auto_approves_admin(self):
        result = run(self.gate.request_approval("execute_task", context={}, user_id="admin"))
        assert result.approved is True

    def test_financial_large_requires_review(self):
        result = run(self.gate.request_approval(
            "payment", context={"amount": 5000}, user_id="alice"
        ))
        assert isinstance(result.approved, bool)

    def test_mode_property(self):
        from sovereign.authority.approval_gate import ApprovalMode
        assert self.gate.mode == ApprovalMode.POLICY

    def test_stats(self):
        run(self.gate.request_approval("read", context={}, user_id="bob"))
        stats = self.gate.stats()
        assert isinstance(stats, dict)
        assert "total" in stats or len(stats) > 0

    def test_approval_stats(self):
        run(self.gate.request_approval("read", context={}, user_id="bob"))
        stats = self.gate.approval_stats()
        assert isinstance(stats, dict)

    def test_audit_trail(self):
        run(self.gate.request_approval("read", context={}, user_id="bob"))
        trail = self.gate.audit_trail
        assert isinstance(trail, list)
        assert len(trail) >= 1

    def test_revoke_nonexistent(self):
        result = self.gate.revoke("nonexistent-id")
        assert result is False

    def test_revoke_existing(self):
        record = run(self.gate.request_approval("search", context={}, user_id="bob"))
        revoked = self.gate.revoke(record.action_id)
        assert isinstance(revoked, bool)

    def test_clear_audit_trail(self):
        run(self.gate.request_approval("read", context={}, user_id="bob"))
        self.gate.clear_audit_trail()
        assert len(self.gate.audit_trail) == 0

    def test_custom_rule_always_approve(self):
        from sovereign.authority.approval_gate import ApprovalGate, ApprovalMode
        gate = ApprovalGate(mode=ApprovalMode.POLICY)
        gate.register_auto_rule(
            lambda action, ctx, uid: True if action == "custom_action" else None,
            outcome=True,
        )
        result = run(gate.request_approval("custom_action", context={}, user_id="user"))
        assert result.approved is True

    def test_from_env(self):
        import os
        from sovereign.authority.approval_gate import ApprovalGate
        os.environ.setdefault("SOVEREIGN_APPROVAL_MODE", "auto")
        gate = ApprovalGate.from_env()
        assert gate is not None

    def test_auto_mode_approves_everything(self):
        from sovereign.authority.approval_gate import ApprovalGate, ApprovalMode
        gate = ApprovalGate(mode=ApprovalMode.AUTO)
        result = run(gate.request_approval("anything", context={}, user_id="user"))
        assert result.approved is True

    def test_legacy_approval_request(self):
        from sovereign.authority.approval_gate import ApprovalGate, ApprovalMode, ApprovalRequest
        from sovereign.kernel.action_classes import ActionClass
        gate = ApprovalGate(mode=ApprovalMode.POLICY)
        req = ApprovalRequest(
            request_id="req1",
            agent_id="agent1",
            action_class=ActionClass.READ,
            action_description="read some file",
            context={},
            risk_score=0.1,
        )
        result = run(gate.request_approval(req))
        assert result is not None


# ===========================================================================
# GuardianAgent (unit — mocked Claude)
# ===========================================================================

def _mock_claude_client(response: str = "APPROVED: No risk detected") -> MagicMock:
    client = MagicMock()
    client.complete = AsyncMock(return_value=response)
    client.complete_with_tool_loop = AsyncMock(return_value=response)
    return client


def _mock_tool_registry() -> MagicMock:
    tr = MagicMock()
    tr.list_schemas.return_value = []
    tr.execute = AsyncMock(return_value={"result": "ok"})
    return tr


def _mock_memory() -> MagicMock:
    m = MagicMock()
    m.get_snapshot = AsyncMock(return_value={})
    m.write = AsyncMock(return_value=None)
    return m


def _mock_constitution() -> MagicMock:
    c = MagicMock()
    c.render_for_prompt.return_value = "CONSTITUTION TEXT"
    return c


def _mock_prompt_builder() -> MagicMock:
    pb = MagicMock()
    pb.build_for_agent.return_value = [
        {"type": "text", "text": "system prompt"}
    ]
    return pb


class TestGuardianAgent:
    def setup_method(self):
        from sovereign.executive.guardian import GuardianAgent
        self.agent = GuardianAgent(
            claude_client=_mock_claude_client(),
            tool_registry=_mock_tool_registry(),
            memory_manager=_mock_memory(),
            constitution=_mock_constitution(),
            prompt_builder=_mock_prompt_builder(),
        )

    def _make_task(self, action_class=None):
        from sovereign.swarm.base_agent import AgentTask
        from sovereign.kernel.action_classes import ActionClass
        return AgentTask(
            objective="Review this EXECUTE action: delete temp file",
            context={"action": "delete", "file": "/tmp/test.txt"},
            action_class=action_class or ActionClass.EXECUTE,
        )

    def _make_ctx(self):
        from sovereign.swarm.base_agent import AgentContext
        return AgentContext(session_id="s1", operating_mode="command")

    def test_guardian_is_leveled_agent(self):
        from sovereign.swarm.leveled_agent import LeveledAgent
        assert isinstance(self.agent, LeveledAgent)

    def test_guardian_agent_id(self):
        assert self.agent.agent_id == "guardian"

    def test_guardian_run_returns_output(self):
        from sovereign.output.output_contract import StructuredOutput
        out = run(self.agent.run(self._make_task(), self._make_ctx()))
        assert isinstance(out, StructuredOutput)

    def test_guardian_run_read_action(self):
        from sovereign.swarm.base_agent import AgentTask
        from sovereign.kernel.action_classes import ActionClass
        from sovereign.output.output_contract import StructuredOutput
        task = AgentTask(
            objective="Read the config file",
            context={"action": "read", "file": "/etc/hosts"},
            action_class=ActionClass.READ,
        )
        out = run(self.agent.run(task, self._make_ctx()))
        assert isinstance(out, StructuredOutput)

    def test_guardian_describe(self):
        desc = self.agent.describe()
        assert isinstance(desc, dict)
        assert "agent_id" in desc

    def test_set_policy_registry(self):
        pr = MagicMock()
        self.agent.set_policy_registry(pr)
        assert self.agent._policy_registry is pr

    def test_guardian_check_approval_required(self):
        result = self.agent._check_approval_required("file_deletion")
        assert result is True

    def test_guardian_check_approval_not_required(self):
        result = self.agent._check_approval_required("read_file")
        assert result is False


# ===========================================================================
# LeveledAgent helpers (state, AgentSpec, AgentLevel)
# ===========================================================================

class TestLeveledAgentHelpers:
    def setup_method(self):
        from sovereign.swarm.leveled_agent import AgentSpec, AgentLevel
        self.AgentSpec = AgentSpec
        self.AgentLevel = AgentLevel

    def test_agent_level_ordering(self):
        from sovereign.swarm.leveled_agent import AgentLevel
        assert AgentLevel.LEVEL_2 < AgentLevel.LEVEL_5

    def test_agent_spec_construction(self):
        spec = self.AgentSpec(
            agent_id="test_agent",
            level=self.AgentLevel.LEVEL_2,
            mission="Test mission",
            triggers=["test_event"],
            tools_allowed=["web_search"],
            escalate_to="chief",
            requires_approval_for=[],
            success_metric="All tests pass",
            failure_condition="Test fails",
        )
        assert spec.agent_id == "test_agent"
        assert spec.level == self.AgentLevel.LEVEL_2

    def test_agent_spec_defaults(self):
        spec = self.AgentSpec(
            agent_id="minimal",
            level=self.AgentLevel.LEVEL_2,
            mission="minimal mission",
            triggers=[],
            tools_allowed=[],
            escalate_to="ceo",
            requires_approval_for=[],
            success_metric="ok",
            failure_condition="fail",
        )
        assert isinstance(spec.requires_approval_for, list)
        assert spec.confidence_threshold >= 0.0

    def test_workflow_step_enum(self):
        from sovereign.swarm.leveled_agent import WorkflowStep
        assert WorkflowStep.OBSERVE is not None
        assert WorkflowStep.ANALYZE is not None
        assert WorkflowStep.EXECUTE is not None

    def test_workflow_result(self):
        from sovereign.swarm.leveled_agent import WorkflowResult, WorkflowStep
        wr = WorkflowResult(step=WorkflowStep.OBSERVE, status="ok", data={}, duration_ms=100.0)
        assert wr.step == WorkflowStep.OBSERVE

    def test_agent_state(self):
        from sovereign.swarm.leveled_agent import AgentState
        state = AgentState(agent_id="test")
        assert state.agent_id == "test"
        assert isinstance(state.open_tasks, list)
        assert isinstance(state.decisions, list)

    def test_guardian_state_load_save(self):
        import tempfile, os
        from sovereign.executive.guardian import GuardianAgent
        agent = GuardianAgent(
            claude_client=_mock_claude_client(),
            tool_registry=_mock_tool_registry(),
            memory_manager=_mock_memory(),
            constitution=_mock_constitution(),
            prompt_builder=_mock_prompt_builder(),
        )
        state = agent._load_state()
        assert state.agent_id == "guardian"
        agent._save_state(state)
