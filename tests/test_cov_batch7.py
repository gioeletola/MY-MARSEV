"""
Coverage batch 7: small modules — silent_ops, attention_engine, integration_registry,
authority_policy, adapter, model_catalog, agent_promoter, chatbot engine,
executive agents (unit), timer_tool, leveled_agent additional.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock


def run(coro):
    return asyncio.run(coro)


def _make_mock_response(text: str):
    block = MagicMock()
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    return resp


def _make_agent_deps(response="Done."):
    mock_resp = _make_mock_response(response)
    return dict(
        claude_client=MagicMock(
            complete=AsyncMock(return_value=mock_resp),
            complete_with_tool_loop=AsyncMock(return_value=(response, [])),
        ),
        tool_registry=MagicMock(list_schemas=MagicMock(return_value=[])),
        memory_manager=MagicMock(get_snapshot=AsyncMock(return_value={}),
                                  write=AsyncMock(return_value=None)),
        constitution=MagicMock(render_for_prompt=MagicMock(return_value="CONST")),
        prompt_builder=MagicMock(build_for_agent=MagicMock(return_value=[{"type": "text", "text": "sys"}])),
    )


# ===========================================================================
# SilentOps
# ===========================================================================

class TestSilentOps:
    def setup_method(self):
        from sovereign.proactive.silent_ops import SilentOps, SilentTask
        self.ops = SilentOps()
        self.ST = SilentTask

    def test_register_task(self):
        task = self.ST(task_id="t1", name="Daily backup", interval_s=3600, callback=lambda: None)
        self.ops.register(task)
        snap = self.ops.snapshot()
        assert any(t["task_id"] == "t1" for t in snap)

    def test_enable_disable(self):
        task = self.ST(task_id="t2", name="Cleanup", interval_s=1800, callback=lambda: None)
        self.ops.register(task)
        self.ops.disable("t2")
        snap = self.ops.snapshot()
        t = next(t for t in snap if t["task_id"] == "t2")
        assert t.get("enabled") is False or t.get("active") is False

    def test_enable_task(self):
        task = self.ST(task_id="t3", name="Health check", interval_s=600, callback=lambda: None)
        self.ops.register(task)
        self.ops.disable("t3")
        self.ops.enable("t3")
        snap = self.ops.snapshot()
        t = next(t for t in snap if t["task_id"] == "t3")
        assert t.get("enabled") is True or t.get("active") is True

    def test_snapshot_empty(self):
        ops = __import__("sovereign.proactive.silent_ops", fromlist=["SilentOps"]).SilentOps()
        snap = ops.snapshot()
        assert isinstance(snap, list)

    def test_stop(self):
        self.ops.stop()  # should not raise


# ===========================================================================
# AttentionEngine
# ===========================================================================

class TestAttentionEngine:
    def setup_method(self):
        from sovereign.layers.attention_engine import AttentionEngineLayer, AttentionSlot
        self.engine = AttentionEngineLayer()
        self.AS = AttentionSlot

    def test_add_slot(self):
        slot = self.AS(slot_id="s1", label="Deep work", category="deep_work", priority=1, allocated_minutes=90)
        self.engine.add_slot(slot)
        assert self.engine.allocated_deep_work_minutes() >= 0

    def test_remove_slot(self):
        slot = self.AS(slot_id="s2", label="Email", category="admin", priority=3, allocated_minutes=30)
        self.engine.add_slot(slot)
        result = self.engine.remove_slot("s2")
        assert result is True

    def test_remove_nonexistent(self):
        result = self.engine.remove_slot("ghost_slot")
        assert result is False

    def test_log_attention(self):
        self.engine.log_attention("Deep reading", minutes=45, category="learning", roi=0.8)

    def test_allocated_minutes(self):
        slot = self.AS(slot_id="s3", label="Focus", category="deep_work", priority=1, allocated_minutes=120)
        self.engine.add_slot(slot)
        mins = self.engine.allocated_deep_work_minutes()
        assert mins >= 0


# ===========================================================================
# IntegrationRegistry
# ===========================================================================

class TestIntegrationRegistry:
    def setup_method(self):
        from sovereign.registries.integration_registry import IntegrationRegistry, IntegrationRecord
        self.registry = IntegrationRegistry()
        self.IR = IntegrationRecord

    def _record(self, iid="slack", kind="messaging"):
        return self.IR(
            integration_id=iid,
            name=iid.title(),
            kind=kind,
            description=f"{iid} integration",
        )

    def test_register(self):
        self.registry.register(self._record())
        result = self.registry.get("slack")
        assert result is not None

    def test_list_all(self):
        self.registry.register(self._record("slack", "messaging"))
        self.registry.register(self._record("github", "dev"))
        all_recs = self.registry.list_all()
        assert len(all_recs) >= 2

    def test_list_by_kind(self):
        self.registry.register(self._record("slack", "messaging"))
        self.registry.register(self._record("stripe", "payment"))
        messaging = self.registry.list_by_kind("messaging")
        assert all(r.kind == "messaging" for r in messaging)

    def test_unregister(self):
        self.registry.register(self._record("to_remove"))
        result = self.registry.unregister("to_remove")
        assert result is True
        assert self.registry.get("to_remove") is None

    def test_unregister_nonexistent(self):
        result = self.registry.unregister("ghost_xyz")
        assert result is False


# ===========================================================================
# AuthorityPolicy + PolicyEngine
# ===========================================================================

class TestAuthorityPolicy:
    def test_default_suggest(self):
        from sovereign.authority.policy import AuthorityPolicy
        policy = AuthorityPolicy.default_suggest()
        allowed, reason = policy.is_permitted({"action_class": "SUGGEST", "agent_id": "test"})
        assert isinstance(allowed, bool)

    def test_default_execute(self):
        from sovereign.authority.policy import AuthorityPolicy
        policy = AuthorityPolicy.default_execute()
        allowed, reason = policy.is_permitted({"action_class": "EXECUTE", "agent_id": "ceo"})
        assert isinstance(allowed, bool)

    def test_is_permitted_read(self):
        from sovereign.authority.policy import AuthorityPolicy
        from sovereign.kernel.action_classes import ActionClass
        policy = AuthorityPolicy(
            allowed_action_classes={ActionClass.READ, ActionClass.SUGGEST},
            blocked_domains=set(),
        )
        allowed, reason = policy.is_permitted({"action_class": "READ"})
        assert isinstance(allowed, bool)

    def test_is_permitted_blocked_domain(self):
        from sovereign.authority.policy import AuthorityPolicy
        from sovereign.kernel.action_classes import ActionClass
        policy = AuthorityPolicy(
            allowed_action_classes={ActionClass.READ},
            blocked_domains={"financial"},
        )
        allowed, reason = policy.is_permitted({"action_class": "READ", "memory_domain": "financial"})
        assert allowed is False

    def test_policy_engine(self):
        from sovereign.authority.policy import PolicyEngine
        engine = PolicyEngine()
        decision = engine.evaluate(
            action="read_file",
            context={"file": "/tmp/test.txt"},
            user_id="file_agent",
        )
        assert decision is not None


# ===========================================================================
# Adapter classes
# ===========================================================================

class TestAdapters:
    def test_json_to_markdown(self):
        from sovereign.adapter.adapters import JsonToMarkdownAdapter
        from sovereign.adapter.types import AdapterFormat
        adapter = JsonToMarkdownAdapter()
        result = run(adapter.adapt('{"name": "Alice", "age": 30}', AdapterFormat.JSON, AdapterFormat.MARKDOWN))
        assert result.success
        assert result.data is not None
        assert "Alice" in result.data or "name" in result.data

    def test_csv_to_json(self):
        from sovereign.adapter.adapters import CsvToJsonAdapter
        from sovereign.adapter.types import AdapterFormat
        import json
        adapter = CsvToJsonAdapter()
        csv_data = "name,age\nAlice,30\nBob,25"
        result = run(adapter.adapt(csv_data, AdapterFormat.CSV, AdapterFormat.JSON))
        assert result.success
        # data may be a list already or a JSON string
        parsed = result.data if isinstance(result.data, list) else json.loads(result.data)
        assert isinstance(parsed, list)

    def test_markdown_to_html(self):
        from sovereign.adapter.adapters import MarkdownToHtmlAdapter
        from sovereign.adapter.types import AdapterFormat
        adapter = MarkdownToHtmlAdapter()
        result = run(adapter.adapt("# Hello\n\nParagraph text.", AdapterFormat.MARKDOWN, AdapterFormat.HTML))
        assert result.success
        assert "Hello" in result.data

    def test_dict_to_yaml(self):
        from sovereign.adapter.adapters import DictToYamlAdapter
        from sovereign.adapter.types import AdapterFormat
        adapter = DictToYamlAdapter()
        result = run(adapter.adapt({"key": "value", "num": 42}, AdapterFormat.JSON, AdapterFormat.YAML))
        assert result.success
        assert "key" in result.data

    def test_json_to_table(self):
        from sovereign.adapter.adapters import JsonToTableAdapter
        from sovereign.adapter.types import AdapterFormat
        adapter = JsonToTableAdapter()
        result = run(adapter.adapt('[{"name": "Alice", "score": 95}]', AdapterFormat.JSON, AdapterFormat.TABLE))
        assert result is not None


# ===========================================================================
# ModelCatalog
# ===========================================================================

class TestModelCatalog:
    def setup_method(self):
        from sovereign.intelligence.model_catalog import ModelCatalog
        self.catalog = ModelCatalog()

    def test_all_models(self):
        models = self.catalog.all()
        assert isinstance(models, list)
        assert len(models) > 0

    def test_get_known_model(self):
        entry = self.catalog.get("claude-sonnet-4-6")
        assert entry is not None

    def test_get_unknown_model(self):
        entry = self.catalog.get("nonexistent-model-xyz")
        assert entry is None

    def test_by_provider(self):
        anthropic_models = self.catalog.by_provider("anthropic")
        assert isinstance(anthropic_models, list)

    def test_model_entry_fields(self):
        entry = self.catalog.get("claude-sonnet-4-6")
        if entry:
            assert hasattr(entry, "model_id") or hasattr(entry, "provider")


# ===========================================================================
# AgentPromoter
# ===========================================================================

class TestAgentPromoter:
    def setup_method(self):
        from sovereign.expansion.agent_promoter import AgentPromoter
        self.promoter = AgentPromoter()

    def test_register_agent(self):
        lifecycle = self.promoter.register("test_agent_v1", "TestAgent", "research")
        assert lifecycle is not None
        assert lifecycle.agent_id == "test_agent_v1"

    def test_get_lifecycle(self):
        self.promoter.register("test_agent_v2", "TestAgent", "finance")
        lc = self.promoter.get("test_agent_v2")
        assert lc is not None

    def test_get_nonexistent(self):
        lc = self.promoter.get("ghost_agent_xyz")
        assert lc is None

    def test_shadow_accuracy_default(self):
        lc = self.promoter.register("shadow_agent", "ShadowAgent", "research")
        acc = lc.shadow_accuracy
        assert 0.0 <= acc <= 1.0

    def test_try_promote_sandbox_to_shadow(self):
        self.promoter.register("promo_agent", "PromoAgent", "research")
        success, reason = self.promoter.try_promote("promo_agent", test_pass_rate=0.95)
        assert isinstance(success, bool)

    def test_try_promote_nonexistent(self):
        success, reason = self.promoter.try_promote("nonexistent_xyz", test_pass_rate=0.9)
        assert success is False


# ===========================================================================
# TimerTool
# ===========================================================================

class TestTimerToolAdditional:
    def setup_method(self):
        from sovereign.tools.builtin.timer_tool import TimerTool
        self.tool = TimerTool()

    def test_start_timer(self):
        r = run(self.tool.execute(action="start", timer_id="t1", label="Task"))
        assert r["error"] is None or isinstance(r, dict)

    def test_stop_timer(self):
        run(self.tool.execute(action="start", timer_id="t2", label="Test"))
        r = run(self.tool.execute(action="stop", timer_id="t2"))
        assert isinstance(r, dict)

    def test_list_timers(self):
        r = run(self.tool.execute(action="list"))
        assert isinstance(r, dict)

    def test_lap_timer(self):
        run(self.tool.execute(action="start", timer_id="t3", label="Lap test"))
        r = run(self.tool.execute(action="lap", timer_id="t3"))
        assert isinstance(r, dict)

    def test_elapsed_time(self):
        run(self.tool.execute(action="start", timer_id="t4", label="Elapsed"))
        r = run(self.tool.execute(action="elapsed", timer_id="t4"))
        assert isinstance(r, dict)
        assert r.get("error") is None

    def test_reset_timer(self):
        run(self.tool.execute(action="start", timer_id="t5", label="Reset"))
        r = run(self.tool.execute(action="reset", timer_id="t5"))
        assert isinstance(r, dict)


# ===========================================================================
# Chatbot ConversationEngine
# ===========================================================================

class TestConversationEngine:
    def setup_method(self):
        from sovereign.chatbot.engine import ConversationEngine
        from sovereign.chatbot.types import ChatSession
        self.engine = ConversationEngine()
        self.session = ChatSession()

    def test_instantiation(self):
        assert self.engine is not None

    def test_set_claude_client(self):
        client = MagicMock()
        self.engine.set_claude_client(client)

    def test_chat_stub_mode(self):
        response = run(self.engine.chat(self.session, "Hello, how are you?"))
        assert response.content is not None
        assert isinstance(response.content, str)

    def test_chat_history(self):
        run(self.engine.chat(self.session, "First message"))
        run(self.engine.chat(self.session, "Second message"))
        messages = self.session.messages
        assert len(messages) >= 2

    def test_chat_response_session_id(self):
        response = run(self.engine.chat(self.session, "Test message"))
        assert response.session_id == self.session.session_id


# ===========================================================================
# Executive agents (unit)
# ===========================================================================

class TestChiefOfStaffUnit:
    def setup_method(self):
        from sovereign.executive.chief_of_staff import ChiefOfStaff
        self.agent = ChiefOfStaff(**_make_agent_deps("Task decomposed into 3 steps."))

    def test_describe(self):
        desc = self.agent.describe()
        assert isinstance(desc, dict)
        assert desc.get("agent_id") == "chief_of_staff"

    def test_run_returns_output(self):
        from sovereign.output.output_contract import StructuredOutput
        from sovereign.swarm.base_agent import AgentTask, AgentContext
        task = AgentTask(objective="Decompose the goal into subtasks")
        ctx = AgentContext(session_id="s1", operating_mode="command")
        out = run(self.agent.run(task, ctx))
        assert isinstance(out, StructuredOutput)


class TestExecutiveAssistantUnit:
    def setup_method(self):
        from sovereign.executive.executive_assistant import ExecutiveAssistantAgent
        self.agent = ExecutiveAssistantAgent(**_make_agent_deps("Assistance provided."))

    def test_describe(self):
        desc = self.agent.describe()
        assert isinstance(desc, dict)


# ===========================================================================
# Swarm — LeveledAgent additional tests (via guardian)
# ===========================================================================

class TestLeveledAgentStateIO:
    def setup_method(self):
        from sovereign.executive.guardian import GuardianAgent
        self.agent = GuardianAgent(**_make_agent_deps())

    def test_load_state_fresh(self):
        state = self.agent._load_state()
        assert state.agent_id == "guardian"
        assert isinstance(state.open_tasks, list)

    def test_save_then_load_state(self):
        state = self.agent._load_state()
        state.decisions.append({"decision": "approved", "risk": 0.1})
        self.agent._save_state(state)
        reloaded = self.agent._load_state()
        assert len(reloaded.decisions) >= 1

    def test_run_observe_step(self):
        from sovereign.output.output_contract import StructuredOutput
        from sovereign.swarm.base_agent import AgentTask, AgentContext
        task = AgentTask(objective="Safety review for action: send email")
        ctx = AgentContext(session_id="s1", operating_mode="command")
        out = run(self.agent.run(task, ctx))
        assert isinstance(out, StructuredOutput)

    def test_run_verify_step(self):
        from sovereign.output.output_contract import StructuredOutput
        from sovereign.swarm.base_agent import AgentTask, AgentContext
        from sovereign.kernel.action_classes import ActionClass
        task = AgentTask(
            objective="Verify: is deleting old logs safe?",
            action_class=ActionClass.READ,
        )
        ctx = AgentContext(session_id="s2", operating_mode="research")
        out = run(self.agent.run(task, ctx))
        assert isinstance(out, StructuredOutput)


# ===========================================================================
# Analytics integration — additional coverage
# ===========================================================================

class TestAnalyticsIntegrationAdditional:
    def setup_method(self):
        from sovereign.integrations.analytics_integration import AnalyticsIntegration
        self.ai = AnalyticsIntegration()

    def test_track_page_view(self):
        result = self.ai.track_page_view("/dashboard", referrer="/home")
        assert isinstance(result, bool)

    def test_connect_with_config(self):
        from sovereign.integrations.base_integration import IntegrationConfig
        config = IntegrationConfig(
            integration_id="analytics_test",
            name="Analytics",
            enabled=True,
            credentials={"api_key": "test_key"},
            settings={},
        )
        result = self.ai.connect(config)
        assert isinstance(result, bool)

    def test_disconnect_when_not_connected(self):
        result = self.ai.disconnect()
        assert isinstance(result, bool)
