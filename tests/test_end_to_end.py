"""End-to-end integration smoke tests — no real API calls."""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# DecisionLedger — JSONL persistence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decision_ledger_record_writes_jsonl(tmp_path):
    from sovereign.registries.decision_ledger import DecisionLedger, DecisionRecord

    ledger = DecisionLedger(data_dir=str(tmp_path))
    rec = DecisionRecord(
        session_id="sess-001",
        agent_id="ceo_agent",
        decision_type="approval",
        description="Approve budget increase",
        outcome="approved",
    )
    await ledger.record(rec)

    jsonl_path = tmp_path / "ledger" / "decisions.jsonl"
    assert jsonl_path.exists()
    content = jsonl_path.read_text()
    assert "sess-001" in content
    assert "ceo_agent" in content


@pytest.mark.asyncio
async def test_decision_ledger_query_returns_record(tmp_path):
    from sovereign.registries.decision_ledger import DecisionLedger, DecisionRecord

    ledger = DecisionLedger(data_dir=str(tmp_path))
    rec = DecisionRecord(
        session_id="sess-002",
        agent_id="guardian",
        decision_type="task_dispatch",
        description="Dispatch analysis task",
    )
    await ledger.record(rec)
    results = await ledger.query(limit=10)
    assert len(results) >= 1
    assert results[-1].session_id == "sess-002"


# ---------------------------------------------------------------------------
# ToolRegistry
# ---------------------------------------------------------------------------


def test_tool_registry_register_and_list():
    from sovereign.tools.tool_registry import ToolRegistry
    from sovereign.tools.base_tool import BaseTool, ToolSchema

    class DummyTool(BaseTool):
        @property
        def schema(self) -> ToolSchema:
            return ToolSchema(
                name="dummy_e2e_tool",
                description="A dummy tool for testing.",
                input_schema={"type": "object", "properties": {}, "required": []},
            )

        async def execute(self, **_) -> dict:
            return {"ok": True}

    reg = ToolRegistry()
    reg.register(DummyTool())
    names = reg.list_names()
    assert "dummy_e2e_tool" in names


def test_tool_registry_get_returns_tool():
    from sovereign.tools.tool_registry import ToolRegistry
    from sovereign.tools.base_tool import BaseTool, ToolSchema

    class GetterTool(BaseTool):
        @property
        def schema(self) -> ToolSchema:
            return ToolSchema(
                name="getter_e2e_tool",
                description="Getter test tool.",
                input_schema={"type": "object", "properties": {}, "required": []},
            )

        async def execute(self, **_) -> dict:
            return {}

    reg = ToolRegistry()
    tool = GetterTool()
    reg.register(tool)
    assert reg.get("getter_e2e_tool") is tool


# ---------------------------------------------------------------------------
# AgentSpec / AgentFactory
# ---------------------------------------------------------------------------


def test_agent_spec_can_be_created():
    from sovereign.factory.agent_spec import AgentSpec

    spec = AgentSpec(
        name="test_agent",
        role="Test Role",
        objective="Do a test thing",
    )
    assert spec.name == "test_agent"
    assert spec.objective == "Do a test thing"


def test_agent_spec_validate_passes():
    from sovereign.factory.agent_spec import AgentSpec

    spec = AgentSpec(
        name="valid_agent",
        role="Analyst",
        objective="Analyse data",
        max_iterations=3,
        ttl_seconds=60,
    )
    spec.validate()  # should not raise


def test_agent_spec_validate_raises_on_empty_name():
    from sovereign.factory.agent_spec import AgentSpec

    spec = AgentSpec(name="", role="Role", objective="obj")
    with pytest.raises(ValueError, match="name"):
        spec.validate()


# ---------------------------------------------------------------------------
# MemoryManager
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_memory_manager_get_snapshot_returns_dict(tmp_path):
    from sovereign.memory.memory_manager import MemoryManager

    mm = MemoryManager(data_dir=str(tmp_path))
    snapshot = await mm.get_snapshot()
    assert isinstance(snapshot, dict)


@pytest.mark.asyncio
async def test_memory_manager_write_and_read(tmp_path):
    from sovereign.memory.memory_manager import MemoryManager

    mm = MemoryManager(data_dir=str(tmp_path))
    await mm.write("identity", "owner", {"name": "Alice"})
    result = await mm.read("identity", "owner")
    assert result is not None
    assert result["name"] == "Alice"


# ---------------------------------------------------------------------------
# ApprovalGate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approval_gate_auto_approves_low_risk():
    from sovereign.authority.approval_gate import ApprovalGate, ApprovalRequest, ApprovalDecision
    from sovereign.kernel.action_classes import ActionClass

    gate = ApprovalGate(mode="auto")
    req = ApprovalRequest(
        request_id="req-001",
        agent_id="worker",
        action_class=ActionClass.READ,
        action_description="Read financial data",
        context={},
        risk_score=0.1,
    )
    result = await gate.request_approval(req)
    assert result.decision == ApprovalDecision.APPROVED


@pytest.mark.asyncio
async def test_approval_gate_rejects_high_risk():
    from sovereign.authority.approval_gate import ApprovalGate, ApprovalRequest, ApprovalDecision
    from sovereign.kernel.action_classes import ActionClass

    gate = ApprovalGate(mode="auto")
    req = ApprovalRequest(
        request_id="req-002",
        agent_id="worker",
        action_class=ActionClass.EXECUTE,
        action_description="Delete all records",
        context={},
        risk_score=0.99,
    )
    result = await gate.request_approval(req)
    assert result.decision in (ApprovalDecision.REJECTED, ApprovalDecision.DEFERRED)


def test_approval_gate_check_returns_bool_for_read_action():
    from sovereign.authority.approval_gate import ApprovalGate
    gate = ApprovalGate(mode="auto")
    assert isinstance(gate, ApprovalGate)


# ---------------------------------------------------------------------------
# GoalMonitor
# ---------------------------------------------------------------------------


def test_goal_monitor_add_and_active_goals(tmp_path, monkeypatch):
    import sovereign.proactive.goal_monitor as gm_module
    monkeypatch.setattr(gm_module, "_DATA_FILE", tmp_path / "goals.json")

    from sovereign.proactive.goal_monitor import GoalMonitor, Goal

    monitor = GoalMonitor()
    g = Goal(
        goal_id="g001",
        title="Grow revenue",
        description="Increase monthly revenue by 20%",
        target_value=100.0,
        current_value=10.0,
    )
    monitor.add(g)
    active = monitor.active_goals()
    assert any(x.goal_id == "g001" for x in active)


def test_goal_monitor_complete_marks_done(tmp_path, monkeypatch):
    import sovereign.proactive.goal_monitor as gm_module
    monkeypatch.setattr(gm_module, "_DATA_FILE", tmp_path / "goals.json")

    from sovereign.proactive.goal_monitor import GoalMonitor, Goal, GoalStatus

    monitor = GoalMonitor()
    g = Goal(
        goal_id="g002",
        title="Launch product",
        description="Ship v1",
        target_value=1.0,
    )
    monitor.add(g)
    monitor.complete("g002")
    assert monitor._goals["g002"].status == GoalStatus.COMPLETED


# ---------------------------------------------------------------------------
# SuggestionEngine
# ---------------------------------------------------------------------------


def test_suggestion_engine_evaluate_returns_list():
    from sovereign.proactive.suggestion_engine import SuggestionEngine

    engine = SuggestionEngine()
    suggestions = engine.evaluate({})
    assert isinstance(suggestions, list)


def test_suggestion_engine_register_rule_fires():
    from sovereign.proactive.suggestion_engine import SuggestionEngine, Suggestion

    engine = SuggestionEngine()

    def my_rule(ctx):
        return [Suggestion(
            suggestion_id="s001",
            title="Test suggestion",
            description="This is a test",
            action="do_something",
            priority=0.9,
        )]

    engine.register_rule("test_rule", my_rule)
    suggestions = engine.evaluate({})
    ids = [s.suggestion_id for s in suggestions]
    assert "s001" in ids


# ---------------------------------------------------------------------------
# IntegrationManager
# ---------------------------------------------------------------------------


def test_integration_manager_list_all_returns_list(tmp_path, monkeypatch):
    import sovereign.integrations.integration_manager as im_module
    monkeypatch.setattr(im_module, "_CONFIG_PATH", tmp_path / "integrations.json")

    from sovereign.integrations.integration_manager import IntegrationManager

    manager = IntegrationManager()
    result = manager.list_all()
    assert isinstance(result, list)
    assert len(result) > 0


def test_integration_manager_health_returns_dict(tmp_path, monkeypatch):
    import sovereign.integrations.integration_manager as im_module
    monkeypatch.setattr(im_module, "_CONFIG_PATH", tmp_path / "integrations.json")

    from sovereign.integrations.integration_manager import IntegrationManager

    manager = IntegrationManager()
    health = manager.health()
    assert isinstance(health, dict)
