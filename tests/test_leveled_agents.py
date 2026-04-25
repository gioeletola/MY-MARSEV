"""
Tests for the Agent Level System — SOVEREIGN AI OS.

Covers:
  - AgentLevel enum values
  - WorkflowStep ordering
  - AgentSpec / AgentState dataclass creation
  - AgentState persistence (save + load round-trip)
  - AgentRegistryMeta: register, lookup, filter by level
  - LeveledAgent 7-step workflow execution
  - Error resilience: step failure does not prevent REPORT
  - CEOAgent spec assertions (LEVEL_3)
  - GuardianAgent spec assertions (requires_approval_for)
"""
from __future__ import annotations

import pathlib
from typing import Any
from unittest.mock import MagicMock

import pytest

from sovereign.output.output_contract import OutputStatus
from sovereign.swarm.agent_registry_meta import (
    AGENT_SPECS,
    agents_by_level,
    get_agent_level,
    register_agent_meta,
)
from sovereign.swarm.base_agent import AgentContext, AgentTask
from sovereign.swarm.leveled_agent import (
    AgentLevel,
    AgentSpec,
    AgentState,
    LeveledAgent,
    WorkflowStep,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx() -> AgentContext:
    return AgentContext(
        session_id="test-session",
        operating_mode="command",
        memory_snapshot={},
        user_id="test-user",
    )


def _make_task(objective: str = "Do a thing") -> AgentTask:
    return AgentTask(objective=objective)


def _make_spec(agent_id: str = "test_agent", level: AgentLevel = AgentLevel.LEVEL_2) -> AgentSpec:
    return AgentSpec(
        agent_id=agent_id,
        level=level,
        mission="Test mission",
        triggers=["test_trigger"],
        tools_allowed=["memory_tool"],
        escalate_to="",
        requires_approval_for=["code_execution"],
        success_metric="Test passed",
        failure_condition="Exception raised",
        confidence_threshold=0.7,
    )


def _make_mock_base_deps() -> dict[str, Any]:
    """Return minimal mocks for BaseAgent.__init__ dependencies."""
    claude_client = MagicMock()
    claude_client.get_usage.return_value = {
        "input": 0, "output": 0, "cache_read": 0, "cache_write": 0
    }
    tool_registry = MagicMock()
    memory_manager = MagicMock()
    constitution = MagicMock()
    prompt_builder = MagicMock()
    return {
        "claude_client": claude_client,
        "tool_registry": tool_registry,
        "memory_manager": memory_manager,
        "constitution": constitution,
        "prompt_builder": prompt_builder,
    }


# ---------------------------------------------------------------------------
# 1. AgentLevel enum values
# ---------------------------------------------------------------------------


def test_agent_level_enum_values():
    """LEVEL_1=1, LEVEL_2=2, LEVEL_3=3."""
    assert AgentLevel.LEVEL_1 == 1
    assert AgentLevel.LEVEL_2 == 2
    assert AgentLevel.LEVEL_3 == 3
    assert AgentLevel.LEVEL_3 > AgentLevel.LEVEL_2 > AgentLevel.LEVEL_1


# ---------------------------------------------------------------------------
# 2. WorkflowStep ordering
# ---------------------------------------------------------------------------


def test_workflow_step_order():
    """Steps must appear in the correct operational sequence."""
    expected_order = [
        WorkflowStep.OBSERVE,
        WorkflowStep.ANALYZE,
        WorkflowStep.PLAN,
        WorkflowStep.EXECUTE,
        WorkflowStep.VERIFY,
        WorkflowStep.REPORT,
        WorkflowStep.SAVE_MEMORY,
    ]
    # Verify all members present
    assert list(WorkflowStep) == expected_order
    # Verify string values are lowercase step names
    assert WorkflowStep.OBSERVE.value == "observe"
    assert WorkflowStep.SAVE_MEMORY.value == "save_memory"


# ---------------------------------------------------------------------------
# 3. AgentSpec creation
# ---------------------------------------------------------------------------


def test_agent_spec_creation():
    """Create an AgentSpec and verify all fields are accessible."""
    spec = _make_spec(agent_id="my_agent", level=AgentLevel.LEVEL_3)

    assert spec.agent_id == "my_agent"
    assert spec.level == AgentLevel.LEVEL_3
    assert spec.mission == "Test mission"
    assert "test_trigger" in spec.triggers
    assert "memory_tool" in spec.tools_allowed
    assert spec.escalate_to == ""
    assert "code_execution" in spec.requires_approval_for
    assert spec.success_metric == "Test passed"
    assert spec.failure_condition == "Exception raised"
    assert spec.confidence_threshold == 0.7


# ---------------------------------------------------------------------------
# 4. AgentState persistence — save and load round-trip
# ---------------------------------------------------------------------------


def test_agent_state_persistence(tmp_path: pathlib.Path):
    """AgentState written by _save_state() can be reloaded by _load_state()."""
    deps = _make_mock_base_deps()

    # Build a minimal concrete LeveledAgent subclass for testing
    class _TestAgent(LeveledAgent):
        agent_id = "test_persist"
        model = "claude-sonnet-4-6"
        spec = _make_spec("test_persist")

    agent = _TestAgent(
        deps["claude_client"],
        deps["tool_registry"],
        deps["memory_manager"],
        deps["constitution"],
        deps["prompt_builder"],
    )

    # Redirect state directory to tmp_path
    import sovereign.swarm.leveled_agent as la_mod
    original_state_dir = la_mod._STATE_DIR
    la_mod._STATE_DIR = tmp_path / "state"

    try:
        state = AgentState(
            agent_id="test_persist",
            open_tasks=[{"id": "t1", "objective": "Do something"}],
            decisions=[{"choice": "A"}],
            errors=[{"msg": "oops"}],
            metrics={"calls": 5},
            history=[{"ts": "2026-01-01T00:00:00Z", "status": "ok"}],
        )
        agent._save_state(state)

        loaded = agent._load_state()
        assert loaded.agent_id == "test_persist"
        assert loaded.open_tasks == [{"id": "t1", "objective": "Do something"}]
        assert loaded.decisions == [{"choice": "A"}]
        assert loaded.errors == [{"msg": "oops"}]
        assert loaded.metrics == {"calls": 5}
        assert len(loaded.history) == 1
        assert loaded.history[0]["status"] == "ok"
    finally:
        la_mod._STATE_DIR = original_state_dir


# ---------------------------------------------------------------------------
# 5. AgentRegistryMeta — register and get
# ---------------------------------------------------------------------------


def test_agent_registry_register_and_get():
    """register_agent_meta() makes the spec retrievable via get_agent_level()."""
    spec = AgentSpec(
        agent_id="registry_test_agent",
        level=AgentLevel.LEVEL_2,
        mission="Registry test",
        triggers=["trigger_x"],
        tools_allowed=["memory_tool"],
        escalate_to="ceo",
        requires_approval_for=[],
        success_metric="Registered",
        failure_condition="Not found",
        confidence_threshold=0.75,
    )
    register_agent_meta(spec)

    assert get_agent_level("registry_test_agent") == AgentLevel.LEVEL_2
    assert AGENT_SPECS["registry_test_agent"].mission == "Registry test"
    assert AGENT_SPECS["registry_test_agent"].escalate_to == "ceo"


def test_get_agent_level_unknown_defaults_to_level_1():
    """Unknown agent_id falls back to LEVEL_1 without raising."""
    level = get_agent_level("nonexistent_agent_xyz_123")
    assert level == AgentLevel.LEVEL_1


# ---------------------------------------------------------------------------
# 6. agents_by_level filter
# ---------------------------------------------------------------------------


def test_agents_by_level_filter():
    """agents_by_level() returns only specs matching the requested level."""
    # Register two agents at different levels
    spec_l2 = AgentSpec(
        agent_id="filter_test_l2",
        level=AgentLevel.LEVEL_2,
        mission="L2 agent",
        triggers=[],
        tools_allowed=[],
        escalate_to="",
        requires_approval_for=[],
        success_metric="",
        failure_condition="",
    )
    spec_l3 = AgentSpec(
        agent_id="filter_test_l3",
        level=AgentLevel.LEVEL_3,
        mission="L3 agent",
        triggers=[],
        tools_allowed=[],
        escalate_to="",
        requires_approval_for=[],
        success_metric="",
        failure_condition="",
    )
    register_agent_meta(spec_l2)
    register_agent_meta(spec_l3)

    l2_ids = {s.agent_id for s in agents_by_level(AgentLevel.LEVEL_2)}
    l3_ids = {s.agent_id for s in agents_by_level(AgentLevel.LEVEL_3)}

    assert "filter_test_l2" in l2_ids
    assert "filter_test_l3" not in l2_ids
    assert "filter_test_l3" in l3_ids
    assert "filter_test_l2" not in l3_ids


# ---------------------------------------------------------------------------
# 7. LeveledAgent run() calls all 7 steps
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_leveled_agent_run_calls_all_steps():
    """All 7 workflow steps must be called when run() executes without errors."""
    deps = _make_mock_base_deps()
    called_steps: list[str] = []

    class _FullAgent(LeveledAgent):
        agent_id = "full_step_test"
        model = "claude-sonnet-4-6"
        spec = _make_spec("full_step_test")

        async def observe(self, task, ctx):
            called_steps.append("observe")
            return {"obs": True}

        async def analyze(self, task, ctx, observations):
            called_steps.append("analyze")
            return {"analysis": True}

        async def plan(self, task, ctx, analysis):
            called_steps.append("plan")
            return {"plan": True}

        async def execute(self, task, ctx, plan):
            called_steps.append("execute")
            return {"executed": True}

        async def verify(self, task, ctx, execution):
            called_steps.append("verify")
            return {"verified": True}

        async def report(self, task, ctx, all_steps):
            called_steps.append("report")
            return self._make_output(task, ctx, "Done", OutputStatus.SUCCESS, confidence=0.9)

        async def save_memory(self, output, ctx):
            called_steps.append("save_memory")

    agent = _FullAgent(
        deps["claude_client"],
        deps["tool_registry"],
        deps["memory_manager"],
        deps["constitution"],
        deps["prompt_builder"],
    )
    task = _make_task()
    ctx = _make_ctx()

    output = await agent.run(task, ctx)

    assert output.status == OutputStatus.SUCCESS
    assert called_steps == [
        "observe", "analyze", "plan", "execute", "verify", "report", "save_memory"
    ]


# ---------------------------------------------------------------------------
# 8. Error in a step does not prevent REPORT from running
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_leveled_agent_error_in_step_continues():
    """An exception in analyze() must not prevent report() from being called."""
    deps = _make_mock_base_deps()
    called: list[str] = []

    class _ErrorAgent(LeveledAgent):
        agent_id = "error_step_test"
        model = "claude-sonnet-4-6"
        spec = _make_spec("error_step_test")

        async def observe(self, task, ctx):
            called.append("observe")
            return {}

        async def analyze(self, task, ctx, observations):
            called.append("analyze")
            raise RuntimeError("Simulated analyze failure")

        async def plan(self, task, ctx, analysis):
            called.append("plan")
            return {}

        async def execute(self, task, ctx, plan):
            called.append("execute")
            return {}

        async def verify(self, task, ctx, execution):
            called.append("verify")
            return {}

        async def report(self, task, ctx, all_steps):
            called.append("report")
            # The analyze step should have failed and be recorded
            analyze_result = all_steps.get("analyze", {})
            return self._make_output(
                task, ctx, "Completed despite analyze error",
                OutputStatus.PARTIAL,
                data={"analyze_data": analyze_result},
                confidence=0.6,
            )

        async def save_memory(self, output, ctx):
            called.append("save_memory")

    agent = _ErrorAgent(
        deps["claude_client"],
        deps["tool_registry"],
        deps["memory_manager"],
        deps["constitution"],
        deps["prompt_builder"],
    )
    output = await agent.run(_make_task(), _make_ctx())

    # All steps must have been called in sequence
    assert "observe" in called
    assert "analyze" in called
    assert "plan" in called
    assert "execute" in called
    assert "verify" in called
    assert "report" in called
    assert "save_memory" in called

    # The analyze step's error must be recorded in the workflow results
    wf = output.data.get("_workflow_results", {})
    assert wf.get("analyze", {}).get("status") == "failed"

    # The output should still be a valid StructuredOutput (not a hard failure)
    assert output.result == "Completed despite analyze error"


# ---------------------------------------------------------------------------
# 9. CEO spec is LEVEL_3
# ---------------------------------------------------------------------------


def test_ceo_spec_is_level_3():
    """CEOAgent.spec.level must be LEVEL_3."""
    from sovereign.executive.ceo_agent import CEOAgent

    assert CEOAgent.spec.level == AgentLevel.LEVEL_3
    assert CEOAgent.spec.agent_id == "ceo"
    assert CEOAgent.spec.confidence_threshold == 0.8
    assert "mode_change" in CEOAgent.spec.requires_approval_for
    assert "resource_allocation" in CEOAgent.spec.requires_approval_for
    assert "new_request" in CEOAgent.spec.triggers


# ---------------------------------------------------------------------------
# 10. Guardian spec requires approval for execute-class actions
# ---------------------------------------------------------------------------


def test_guardian_spec_requires_approval():
    """GuardianAgent.spec must require approval for all EXECUTE-type actions."""
    from sovereign.executive.guardian import GuardianAgent

    spec = GuardianAgent.spec
    assert spec.level == AgentLevel.LEVEL_3
    assert spec.agent_id == "guardian"
    assert spec.escalate_to == "ceo"

    required = spec.requires_approval_for
    assert "external_api_call" in required
    assert "file_deletion" in required
    assert "send_message" in required
    assert "code_execution" in required

    assert spec.success_metric == "No unsafe actions pass through"
    assert "10%" in spec.failure_condition
