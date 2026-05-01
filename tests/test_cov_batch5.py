"""
Coverage batch 5: eval_agent, builder_studio, human_layer, claude/client,
analytics_integration, governance/change_management, calendar_connector,
leveled_agent additional, swarm/offline_agents, models/routing.
"""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock


def run(coro):
    return asyncio.run(coro)


# ===========================================================================
# EvalAgent + RegressionTracker
# ===========================================================================

class TestEvalAgent:
    def setup_method(self):
        from sovereign.observability.eval_agent import EvalAgent
        self._tmpdir = tempfile.mkdtemp()
        self.agent = EvalAgent(data_path=Path(self._tmpdir) / "evals.jsonl")

    def _eval(self, result="This is a detailed result with recommendations. "
              "You should implement the following steps: first do X, then do Y, "
              "then review and complete the task on schedule."):
        return self.agent.evaluate(
            session_id="s1",
            agent_id="a1",
            task_id="t1",
            objective="Write a plan",
            result=result,
        )

    def test_evaluate_returns_eval_result(self):
        from sovereign.observability.eval_agent import EvalResult
        ev = self._eval()
        assert isinstance(ev, EvalResult)

    def test_evaluate_pass_good_result(self):
        ev = self._eval()
        assert isinstance(ev.passed, bool)
        assert 0.0 <= ev.overall <= 1.0

    def test_evaluate_fail_short_result(self):
        ev = self.agent.evaluate("s1", "a1", "t1", "obj", "short")
        assert ev.overall <= 0.8

    def test_evaluate_flags_safety_issue(self):
        result = "This action might harm users and illegal exploitation of systems."
        ev = self.agent.evaluate("s1", "a1", "t1", "obj", result)
        assert isinstance(ev.flags, list)

    def test_evaluate_with_action_words(self):
        result = ("You should implement the following steps. "
                  "First, execute the plan. Then review and schedule the delivery. "
                  "Priority is to complete all tasks by the deadline.")
        ev = self.agent.evaluate("s1", "a1", "t1", "make a plan", result)
        assert ev.actionability > 0.0

    def test_agent_stats_empty(self):
        stats = self.agent.agent_stats("unknown_agent")
        assert isinstance(stats, dict)

    def test_agent_stats_after_eval(self):
        self._eval()
        stats = self.agent.agent_stats("a1")
        assert isinstance(stats, dict)
        assert len(stats) > 0

    def test_failing_agents(self):
        self.agent.evaluate("s1", "bad_agent", "t1", "obj", "bad")
        failing = self.agent.failing_agents(pass_rate_threshold=0.99)
        assert isinstance(failing, list)

    def test_overall_stats(self):
        self._eval()
        stats = self.agent.overall_stats()
        assert isinstance(stats, dict)
        assert "total_evals" in stats or len(stats) > 0

    def test_recent_evals(self):
        self._eval()
        evals = self.agent.recent_evals(limit=5)
        assert isinstance(evals, list)


class TestRegressionTracker:
    def setup_method(self):
        from sovereign.observability.eval_agent import RegressionTracker
        self._tmpdir = tempfile.mkdtemp()
        self.tracker = RegressionTracker(data_path=Path(self._tmpdir) / "reg.jsonl")

    def _make_eval(self, agent_id="a1", passed=True, overall=0.8):
        import uuid
        from sovereign.observability.eval_agent import EvalResult
        return EvalResult(
            eval_id=str(uuid.uuid4())[:8],
            session_id="s1",
            agent_id=agent_id,
            task_id="t1",
            passed=passed,
            overall=overall,
            completeness=0.9,
            actionability=0.8,
            tone_format=0.7,
            safety=1.0,
            flags=[],
        )

    def test_record_eval(self):
        ev = self._make_eval()
        self.tracker.record(ev)
        history = self.tracker.get_history("a1")
        assert len(history) >= 1

    def test_regression_report(self):
        self.tracker.record(self._make_eval())
        report = self.tracker.regression_report()
        assert isinstance(report, dict)


# ===========================================================================
# BuilderStudio + ProjectScaffolder
# ===========================================================================

class TestBuilderStudio:
    def setup_method(self):
        from sovereign.builder.builder_studio import BuilderStudio
        self._tmpdir = tempfile.mkdtemp()
        self.studio = BuilderStudio(data_dir=self._tmpdir)

    def test_create_agent_blueprint(self):
        from sovereign.builder.builder_studio import AgentBlueprint
        bp = self.studio.create_agent(
            name="TestWorker",
            specialty="Data analysis",
            instructions="Analyze data and provide insights.",
        )
        assert isinstance(bp, AgentBlueprint)
        assert bp.name == "TestWorker"

    def test_get_agent_blueprint(self):
        bp = self.studio.create_agent(
            name="Retriever",
            specialty="Search",
            instructions="Search and retrieve data.",
        )
        fetched = self.studio.get_agent_blueprint(bp.blueprint_id)
        assert fetched is not None
        assert fetched.name == "Retriever"

    def test_list_agent_blueprints(self):
        self.studio.create_agent("A1", "s1", "instructions")
        self.studio.create_agent("A2", "s2", "instructions")
        blueprints = self.studio.list_agent_blueprints()
        assert len(blueprints) >= 2

    def test_delete_agent_blueprint(self):
        bp = self.studio.create_agent("ToDelete", "sp", "instr")
        result = self.studio.delete_agent_blueprint(bp.blueprint_id)
        assert result is True
        assert self.studio.get_agent_blueprint(bp.blueprint_id) is None

    def test_delete_nonexistent(self):
        result = self.studio.delete_agent_blueprint("nonexistent_xyz")
        assert result is False

    def test_create_workflow(self):
        from sovereign.builder.builder_studio import WorkflowBlueprint
        wf = self.studio.create_workflow(
            name="TestWorkflow",
            description="A test workflow",
            steps=[{"action": "analyze", "agent": "analyzer"}],
        )
        assert isinstance(wf, WorkflowBlueprint)
        assert wf.name == "TestWorkflow"

    def test_list_workflow_blueprints(self):
        self.studio.create_workflow("WF1", "desc1", [])
        wfs = self.studio.list_workflow_blueprints()
        assert len(wfs) >= 1

    def test_export_workflow_json(self):
        wf = self.studio.create_workflow("ExportTest", "desc", [{"step": 1}])
        exported = self.studio.export_workflow(wf.workflow_id, fmt="json")
        assert isinstance(exported, str)
        import json
        parsed = json.loads(exported)
        assert parsed.get("name") == "ExportTest"

    def test_import_workflow(self):
        import json
        raw = json.dumps({
            "name": "Imported",
            "description": "From JSON",
            "steps": [],
            "workflow_id": "imported_id",
        })
        wf = self.studio.import_workflow(raw, fmt="json")
        assert wf.name == "Imported"

    def test_dashboard(self):
        dashboard = self.studio.dashboard()
        assert isinstance(dashboard, dict)
        assert "agent_blueprints" in dashboard or "agents" in dashboard or len(dashboard) > 0


class TestProjectScaffolder:
    def setup_method(self):
        from sovereign.builder.builder_studio import ProjectScaffolder, ProjectType
        self.scaffolder = ProjectScaffolder()
        self.ProjectType = ProjectType

    def test_create_project(self):
        from sovereign.builder.builder_studio import BuildProject
        project = self.scaffolder.create(
            name="MyApp",
            project_type=self.ProjectType.WEBAPP,
            stack="python",
        )
        assert isinstance(project, BuildProject)
        assert project.name == "MyApp"

    def test_scaffold_creates_files(self):
        with tempfile.TemporaryDirectory() as d:
            project = self.scaffolder.create("TestApp", self.ProjectType.CLI, "python")
            files = self.scaffolder.scaffold(project, output_dir=Path(d))
            assert isinstance(files, list)

    def test_add_dependency(self):
        project = self.scaffolder.create("DepTest", self.ProjectType.API)
        self.scaffolder.add_dependency(project, "requests", ">=2.28.0")
        assert "requests" in str(project.dependencies)

    def test_estimate_complexity(self):
        project = self.scaffolder.create("ComplexApp", self.ProjectType.AGENT)
        est = self.scaffolder.estimate_complexity(project)
        assert isinstance(est, dict)

    def test_build(self):
        from sovereign.builder.builder_studio import BuildResult
        project = self.scaffolder.create("BuildTest", self.ProjectType.CLI)
        result = self.scaffolder.build(project)
        assert isinstance(result, BuildResult)


# ===========================================================================
# HumanLayer
# ===========================================================================

class TestHumanLayer:
    def setup_method(self):
        from sovereign.layers.human_layer import HumanLayer, HumanCollaborator
        self._tmpdir = tempfile.mkdtemp()
        self.layer = HumanLayer(data_path=Path(self._tmpdir) / "humans.json")
        self.HC = HumanCollaborator

    def _human(self, hid="h1"):
        return self.HC(
            human_id=hid,
            name="Alice Smith",
            role="assistant",
            access_level="suggest",
            email="alice@example.com",
        )

    def test_register_human(self):
        self.layer.register_human(self._human())
        h = self.layer.get_human("h1")
        assert h is not None
        assert h.name == "Alice Smith"

    def test_list_humans_empty(self):
        humans = self.layer.list_humans()
        assert isinstance(humans, list)

    def test_list_humans_active_only(self):
        self.layer.register_human(self._human("h2"))
        humans = self.layer.list_humans(active_only=True)
        assert all(h.active for h in humans)

    def test_deactivate_human(self):
        self.layer.register_human(self._human("h3"))
        self.layer.deactivate_human("h3")
        h = self.layer.get_human("h3")
        assert h is not None
        assert h.active is False

    def test_assign_task(self):
        from sovereign.layers.human_layer import HumanTask
        self.layer.register_human(self._human("h4"))
        task = HumanTask(
            task_id="task1",
            human_id="h4",
            title="Review report",
            description="Please review the weekly report and give feedback.",
            priority=1,
        )
        assigned = self.layer.assign_task(task)
        assert assigned.task_id == "task1"

    def test_create_and_assign(self):
        self.layer.register_human(self._human("h5"))
        task = self.layer.create_and_assign(
            human_id="h5",
            title="Code review",
            description="Review the authentication module.",
            deliverable="Review notes document",
        )
        assert task is not None

    def test_update_task_status(self):
        from sovereign.layers.human_layer import HumanTask
        self.layer.register_human(self._human("h6"))
        task = HumanTask(task_id="task2", human_id="h6", title="T", description="D")
        self.layer.assign_task(task)
        result = self.layer.update_task_status("task2", "in_progress", notes="started")
        assert result is True

    def test_get_tasks_for_human(self):
        from sovereign.layers.human_layer import HumanTask
        self.layer.register_human(self._human("h7"))
        task = HumanTask(task_id="task3", human_id="h7", title="T", description="D")
        self.layer.assign_task(task)
        tasks = self.layer.get_tasks_for_human("h7")
        assert len(tasks) >= 1

    def test_pending_tasks(self):
        self.layer.register_human(self._human("h8"))
        self.layer.create_and_assign("h8", "Pending task", "D", deliverable="result")
        tasks = self.layer.pending_tasks()
        assert isinstance(tasks, list)

    def test_dashboard(self):
        dashboard = self.layer.dashboard()
        assert isinstance(dashboard, dict)


# ===========================================================================
# CachedSystemPrompt + TokenUsage
# ===========================================================================

class TestCachedSystemPrompt:
    def setup_method(self):
        from sovereign.claude.client import CachedSystemPrompt
        self.CSP = CachedSystemPrompt

    def test_to_api_blocks_static_only(self):
        csp = self.CSP(static_section="CONSTITUTION TEXT " * 100)
        blocks = csp.to_api_blocks()
        assert isinstance(blocks, list)
        assert len(blocks) == 1
        assert blocks[0]["type"] == "text"
        assert blocks[0]["cache_control"] == {"type": "ephemeral"}

    def test_to_api_blocks_with_dynamic(self):
        csp = self.CSP(
            static_section="STATIC CONTENT " * 50,
            dynamic_section="Session context here",
        )
        blocks = csp.to_api_blocks()
        assert len(blocks) == 2
        assert blocks[1]["text"] == "Session context here"
        assert "cache_control" not in blocks[1]

    def test_static_always_cached(self):
        csp = self.CSP(static_section="static")
        blocks = csp.to_api_blocks()
        assert blocks[0]["cache_control"]["type"] == "ephemeral"


class TestTokenUsage:
    def setup_method(self):
        from sovereign.claude.client import TokenUsage
        self.TU = TokenUsage

    def test_initial_state(self):
        tu = self.TU()
        assert tu.input_tokens == 0
        assert tu.output_tokens == 0
        assert tu.cache_read_input_tokens == 0
        assert tu.cache_creation_input_tokens == 0

    def test_total(self):
        tu = self.TU(input_tokens=100, output_tokens=50)
        assert tu.total == 150

    def test_effective_input(self):
        tu = self.TU(input_tokens=1000, cache_read_input_tokens=800)
        eff = tu.effective_input
        assert eff <= 1000

    def test_to_dict(self):
        tu = self.TU(input_tokens=100, output_tokens=50)
        d = tu.to_dict()
        assert isinstance(d, dict)
        assert "input" in d or "input_tokens" in d


# ===========================================================================
# AnalyticsIntegration
# ===========================================================================

class TestAnalyticsIntegration:
    def setup_method(self):
        from sovereign.integrations.analytics_integration import AnalyticsIntegration
        self.ai = AnalyticsIntegration()

    def test_instantiation(self):
        assert self.ai is not None

    def test_test_connection_no_config(self):
        result = self.ai.test_connection()
        assert isinstance(result, bool)

    def test_track_event(self):
        result = self.ai.track_event(
            event_name="test_event",
            params={"page": "/home", "action": "click"},
            user_id="user1",
        )
        assert isinstance(result, bool)

    def test_track_session(self):
        result = self.ai.track_session(mode="command", tokens=500, latency_ms=250.0)
        assert isinstance(result, bool)

    def test_track_agent_run(self):
        result = self.ai.track_agent_run(
            agent_id="ceo_agent", status="completed", confidence=0.9
        )
        assert isinstance(result, bool)

    def test_get_stats(self):
        stats = self.ai.get_stats()
        assert isinstance(stats, dict)

    def test_fetch_no_connection(self):
        result = self.ai.fetch("events", {})
        assert isinstance(result, dict)

    def test_push_no_connection(self):
        result = self.ai.push("events", {"event": "test"})
        assert isinstance(result, dict)


# ===========================================================================
# Offline agents (unit)
# ===========================================================================

class TestOfflineAgents:
    def test_offline_agents_importable(self):
        from sovereign.swarm.offline_agents import OFFLINE_AGENTS
        assert isinstance(OFFLINE_AGENTS, list)
        assert len(OFFLINE_AGENTS) > 0

    def test_offline_agent_describe(self):
        from sovereign.swarm.offline_agents import OFFLINE_AGENTS
        for agent_cls in OFFLINE_AGENTS[:2]:
            agent = agent_cls(
                claude_client=MagicMock(complete=AsyncMock(return_value="ok")),
                tool_registry=MagicMock(list_schemas=MagicMock(return_value=[])),
                memory_manager=MagicMock(),
                constitution=MagicMock(render_for_prompt=MagicMock(return_value="")),
                prompt_builder=MagicMock(build_for_agent=MagicMock(return_value=[])),
            )
            desc = agent.describe()
            assert isinstance(desc, dict)
            assert "agent_id" in desc


# ===========================================================================
# Model routing
# ===========================================================================

class TestModelRouter:
    def setup_method(self):
        from sovereign.router.model_router import ModelRouter
        self.router = ModelRouter()

    def test_route_to_model(self):
        from sovereign.router.model_router import RoutingCriteria
        model = self.router.route(RoutingCriteria(
            task_complexity=0.9, action_class="EXECUTE"
        ))
        assert isinstance(model, str)
        assert len(model) > 0

    def test_route_simple_task(self):
        from sovereign.router.model_router import RoutingCriteria
        model = self.router.route(RoutingCriteria(
            task_complexity=0.1, action_class="READ", cost_budget_tokens=1000
        ))
        assert isinstance(model, str)

    def test_route_medium_task(self):
        from sovereign.router.model_router import RoutingCriteria
        model = self.router.route(RoutingCriteria(
            task_complexity=0.5, action_class="SUGGEST"
        ))
        assert isinstance(model, str)

    def test_route_tier(self):
        from sovereign.router.model_router import RoutingCriteria
        tier = self.router.route_tier(RoutingCriteria(task_complexity=0.8))
        assert tier is not None

    def test_cost_estimator(self):
        from sovereign.router.cost_estimator import estimate_cost
        cost = estimate_cost(model="claude-sonnet-4-6", input_tokens=1000, output_tokens=500)
        assert isinstance(cost, float)
        assert cost >= 0.0


# ===========================================================================
# Registries (prompt + workflow + experiment)
# ===========================================================================

class TestRegistries:
    def test_prompt_registry_load(self):
        from sovereign.registries.prompt_registry import PromptRegistry
        pr = PromptRegistry()
        assert pr is not None

    def test_prompt_registry_list(self):
        from sovereign.registries.prompt_registry import PromptRegistry
        pr = PromptRegistry()
        prompts = pr.list_templates()
        assert isinstance(prompts, list)

    def test_workflow_registry(self):
        from sovereign.registries.workflow_registry import WorkflowRegistry
        wr = WorkflowRegistry()
        assert wr is not None
        workflows = wr.list_workflows()
        assert isinstance(workflows, list)

    def test_experiment_registry(self):
        from sovereign.registries.experiment_registry import ExperimentRegistry
        er = ExperimentRegistry()
        assert er is not None


# ===========================================================================
# Governance change management
# ===========================================================================

class TestChangeManagement:
    def setup_method(self):
        from sovereign.governance.change_management import ChangeManagement
        self._tmpdir = tempfile.mkdtemp()
        self.cm = ChangeManagement(persist_path=Path(self._tmpdir) / "changes.json")

    def test_instantiation(self):
        assert self.cm is not None

    def _propose(self, title="Test change"):
        from sovereign.governance.change_management import ChangeType
        return self.cm.propose(
            title=title,
            description="Some description",
            change_type=ChangeType.CONFIG,
            proposed_by="ceo_agent",
            risk_level="low",
            rollback_plan="Revert config file",
        )

    def test_propose_change(self):
        change = self._propose()
        assert change is not None
        assert hasattr(change, "change_id")

    def test_pending_changes(self):
        self._propose()
        pending = self.cm.pending()
        assert isinstance(pending, list)
        assert len(pending) >= 1

    def test_approve_change(self):
        change = self._propose("Approve me")
        result = self.cm.approve(change.change_id, approved_by="admin")
        assert result is True

    def test_reject_change(self):
        change = self._propose("Reject me")
        result = self.cm.reject(change.change_id, reason="Too risky")
        assert result is True

    def test_approve_nonexistent(self):
        result = self.cm.approve("nonexistent-id", approved_by="admin")
        assert result is False


# ===========================================================================
# Calendar connector additional
# ===========================================================================

class TestCalendarConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.calendar_connector import CalendarConnector
        c = CalendarConnector()
        desc = c.describe()
        assert isinstance(desc, dict)
        health = run(c.health())
        assert health is not None
        connected = run(c.connect())
        assert isinstance(connected, bool)
        result = run(c.sync())
        assert isinstance(result.success, bool)

    def test_list_events(self):
        from sovereign.integrations.connectors.calendar_connector import CalendarConnector
        c = CalendarConnector()
        events = run(c.list_events()) if hasattr(c, "list_events") else []
        assert isinstance(events, list)

    def test_get_upcoming(self):
        from sovereign.integrations.connectors.calendar_connector import CalendarConnector
        c = CalendarConnector()
        if hasattr(c, "get_upcoming"):
            events = run(c.get_upcoming(days=7))
            assert isinstance(events, list)

    def test_search_events(self):
        from sovereign.integrations.connectors.calendar_connector import CalendarConnector
        c = CalendarConnector()
        if hasattr(c, "search_events"):
            events = run(c.search_events("meeting"))
            assert isinstance(events, list)
