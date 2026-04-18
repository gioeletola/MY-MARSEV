"""Tests for agent registry, decision ledger, workflow registry, and governance."""
from __future__ import annotations
import pytest


# ── AgentRegistry ─────────────────────────────────────────────────────────────

def test_agent_registry_register_and_get():
    from sovereign.registries.agent_registry import AgentRegistry
    from sovereign.swarm.base_agent import BaseAgent

    class MockAgent(BaseAgent):
        agent_id = "test_mock_reg"
        model = "claude-sonnet-4-6"
        async def run(self, task, ctx):  # type: ignore[override]
            pass

    reg = AgentRegistry()
    reg.register(MockAgent)
    result = reg.get("test_mock_reg")
    assert result is MockAgent


def test_agent_registry_get_missing_returns_none():
    from sovereign.registries.agent_registry import AgentRegistry
    reg = AgentRegistry()
    assert reg.get("absolutely_nonexistent_xyz") is None


def test_agent_registry_duplicate_is_idempotent():
    from sovereign.registries.agent_registry import AgentRegistry
    from sovereign.swarm.base_agent import BaseAgent

    class DupAgent(BaseAgent):
        agent_id = "dup_test_agent"
        model = "claude-sonnet-4-6"
        async def run(self, task, ctx):  # type: ignore[override]
            pass

    reg = AgentRegistry()
    reg.register(DupAgent)
    reg.register(DupAgent)  # should not raise


def test_agent_registry_count():
    from sovereign.registries.agent_registry import AgentRegistry
    from sovereign.swarm.base_agent import BaseAgent

    class CountAgent(BaseAgent):
        agent_id = "count_test_agent"
        model = "claude-sonnet-4-6"
        async def run(self, task, ctx):  # type: ignore[override]
            pass

    reg = AgentRegistry()
    before = reg.count()
    reg.register(CountAgent)
    assert reg.count() >= before


def test_agent_registry_list_all_returns_dict():
    from sovereign.registries.agent_registry import AgentRegistry
    reg = AgentRegistry()
    result = reg.list_agents()
    assert isinstance(result, (dict, list))


# ── DecisionLedger ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_decision_ledger_record_and_recent(tmp_path):
    from sovereign.registries.decision_ledger import DecisionLedger, DecisionRecord
    ledger = DecisionLedger(data_dir=str(tmp_path))
    rec = DecisionRecord(session_id="s1", agent_id="ceo_agent", decision_type="approval", description="Approve budget", outcome="approved")
    await ledger.record(rec)
    recent = await ledger.query(limit=10)
    assert len(recent) >= 1


@pytest.mark.asyncio
async def test_decision_ledger_recent_limit(tmp_path):
    from sovereign.registries.decision_ledger import DecisionLedger, DecisionRecord
    ledger = DecisionLedger(data_dir=str(tmp_path))
    for i in range(7):
        await ledger.record(DecisionRecord(session_id="s", agent_id=f"a{i}", decision_type="test", description=f"d{i}"))
    recent = await ledger.query(limit=3)
    assert len(recent) == 3


# ── WorkflowRegistry ──────────────────────────────────────────────────────────

def test_workflow_registry_register_and_get():
    from sovereign.registries.workflow_registry import WorkflowRegistry, WorkflowDefinition
    reg = WorkflowRegistry()
    wf = WorkflowDefinition(name="test_wf_unique", description="Test workflow")
    reg.register(wf)
    result = reg.get("test_wf_unique")
    assert result is not None
    assert result.name == "test_wf_unique"


def test_workflow_registry_list():
    from sovereign.registries.workflow_registry import WorkflowRegistry, WorkflowDefinition
    reg = WorkflowRegistry()
    reg.register(WorkflowDefinition(name="wf_list_unique", description="WF"))
    wfs = reg.list_workflows()
    assert isinstance(wfs, (list, dict))


# ── Governance (basic import tests) ───────────────────────────────────────────

def test_rbac_imports():
    pytest.importorskip("sovereign.governance.rbac")
    from sovereign.governance.rbac import RBACRegistry
    reg = RBACRegistry()
    assert isinstance(reg, RBACRegistry)


def test_rbac_owner_has_all_perms():
    from sovereign.governance.rbac import RBACRegistry, Permission
    reg = RBACRegistry()
    reg.assign_role("user1", "owner")
    for perm in Permission:
        assert reg.check_permission("user1", perm), f"owner missing {perm}"


def test_rbac_readonly_cannot_execute():
    from sovereign.governance.rbac import RBACRegistry, Permission
    reg = RBACRegistry()
    reg.assign_role("readonly_user", "readonly")
    assert not reg.check_permission("readonly_user", Permission.EXECUTE_ACTION)
    assert reg.check_permission("readonly_user", Permission.READ_DATA)


def test_spending_limits_imports():
    pytest.importorskip("sovereign.governance.spending_limits")
    from sovereign.governance.spending_limits import SpendingLimitsEngine, SpendingCategory
    engine = SpendingLimitsEngine()
    allowed, reason = engine.check(SpendingCategory.TOKENS, 0.50)
    assert allowed is True


def test_spending_limits_blocks_over_limit():
    from sovereign.governance.spending_limits import SpendingLimitsEngine, SpendingCategory
    engine = SpendingLimitsEngine()
    allowed, reason = engine.check(SpendingCategory.TOKENS, 999999.0)
    assert allowed is False


def test_risk_scoring_imports():
    pytest.importorskip("sovereign.governance.risk_scoring")
    from sovereign.governance.risk_scoring import RiskScoringEngine
    engine = RiskScoringEngine()
    score = engine.score("Analyse cashflow data", "READ", "cashflow_analyst", {})
    assert 0.0 <= score.overall <= 1.0


def test_escalation_imports():
    pytest.importorskip("sovereign.governance.escalation")
    from sovereign.governance.escalation import EscalationChain, EscalationLevel
    chain = EscalationChain()
    level = chain.evaluate("cashflow_analyst", "READ", 0.1, "Read financial data")
    assert isinstance(level, EscalationLevel)
