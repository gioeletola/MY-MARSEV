"""
Integration smoke-tests for the orchestrator.

These tests mock the Claude API so no real ANTHROPIC_API_KEY is needed.
"""
from __future__ import annotations

import pytest

from sovereign.output.output_contract import OutputStatus, StructuredOutput
from sovereign.tools.tool_registry import ToolRegistry
from sovereign.memory.memory_manager import MemoryManager
from sovereign.registries.decision_ledger import DecisionLedger, DecisionRecord
from sovereign.authority.thresholds import EscalationThresholds


class TestStructuredOutput:
    def test_failure_factory(self):
        out = StructuredOutput.failure("s1", "worker", "t1", "something broke")
        assert out.status == OutputStatus.FAILED
        assert "something broke" in out.result
        assert out.error == "something broke"

    def test_escalated_factory(self):
        out = StructuredOutput.escalated("s1", "guardian", "t1", "high risk")
        assert out.status == OutputStatus.ESCALATED
        assert out.requires_human_review is True

    def test_to_dict_serialisable(self):
        import json
        out = StructuredOutput(
            session_id="s1",
            agent_id="worker",
            task_id="t1",
            status=OutputStatus.SUCCESS,
            result="Done",
        )
        d = out.to_dict()
        # Must be JSON-serialisable
        json.dumps(d)

    def test_add_tokens(self):
        out = StructuredOutput(
            session_id="s1", agent_id="a", task_id="t",
            status=OutputStatus.SUCCESS, result="ok"
        )
        out.add_tokens({"input": 100, "output": 50, "cache_read": 200})
        assert out.tokens_used["input"] == 100
        assert out.tokens_used["cache_read"] == 200


class TestToolRegistry:
    def test_register_and_get(self):
        from sovereign.tools.builtin.web_search import WebSearchTool
        registry = ToolRegistry()
        tool = WebSearchTool()
        registry.register(tool)
        assert registry.get("web_search") is tool

    def test_duplicate_raises(self):
        from sovereign.tools.builtin.web_search import WebSearchTool
        registry = ToolRegistry()
        registry.register(WebSearchTool())
        with pytest.raises(ValueError, match="already registered"):
            registry.register(WebSearchTool())

    def test_list_schemas_empty_allowed(self):
        from sovereign.tools.builtin.web_search import WebSearchTool
        registry = ToolRegistry()
        registry.register(WebSearchTool())
        schemas = registry.list_schemas(allowed=[])
        assert schemas == []

    def test_list_schemas_all(self):
        from sovereign.tools.builtin.web_search import WebSearchTool
        registry = ToolRegistry()
        registry.register(WebSearchTool())
        schemas = registry.list_schemas()
        assert len(schemas) == 1
        assert schemas[0]["name"] == "web_search"

    @pytest.mark.asyncio
    async def test_execute_web_search_stub(self):
        from sovereign.tools.builtin.web_search import WebSearchTool
        registry = ToolRegistry()
        registry.register(WebSearchTool())
        result = await registry.execute("web_search", {"query": "test"})
        assert isinstance(result, list)
        assert len(result) >= 1


class TestEscalationThresholds:
    def test_for_finance_mode_very_strict(self):
        t = EscalationThresholds.for_mode("finance")
        assert t.auto_approve_below_risk < 0.1
        assert t.escalate_above_risk < 0.5

    def test_for_survival_mode_lenient(self):
        t = EscalationThresholds.for_mode("survival")
        assert t.auto_approve_below_risk >= 0.4

    def test_should_auto_approve(self):
        t = EscalationThresholds(auto_approve_below_risk=0.2)
        assert t.should_auto_approve(0.1)
        assert not t.should_auto_approve(0.3)

    def test_should_escalate(self):
        t = EscalationThresholds(escalate_above_risk=0.7)
        assert t.should_escalate(0.8)
        assert not t.should_escalate(0.5)


@pytest.mark.asyncio
async def test_decision_ledger_roundtrip(tmp_path):
    ledger = DecisionLedger(data_dir=str(tmp_path))
    record = DecisionRecord(
        session_id="s1",
        agent_id="ceo",
        decision_type="task_dispatch",
        description="Test decision",
        outcome="success",
        confidence=0.9,
    )
    await ledger.record(record)
    results = await ledger.query(session_id="s1")
    assert len(results) == 1
    assert results[0].description == "Test decision"


@pytest.mark.asyncio
async def test_memory_manager_read_write(tmp_path):
    memory = MemoryManager(data_dir=str(tmp_path))
    await memory.write("identity", "user_001", {"name": "Test User", "org": "MARSEV"})
    record = await memory.read("identity", "user_001")
    assert record is not None
    assert record["name"] == "Test User"


@pytest.mark.asyncio
async def test_memory_manager_semantic_search(tmp_path):
    memory = MemoryManager(data_dir=str(tmp_path))
    await memory.write("research", "r1", {"title": "AI operating systems survey"})
    await memory.write("research", "r2", {"title": "Financial modelling techniques"})
    results = await memory.semantic_search("AI operating")
    assert any("AI" in str(r) for r in results)
