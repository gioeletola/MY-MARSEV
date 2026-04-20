"""
Tests for low-coverage registry modules and the enhanced ModelRouter.
"""
from __future__ import annotations

import pytest


# ===========================================================================
# PromptRegistry
# ===========================================================================

class TestPromptRegistry:
    @pytest.fixture
    def registry(self, tmp_path):
        from sovereign.registries.prompt_registry import PromptRegistry
        prompts_dir = tmp_path / "prompts"
        (prompts_dir / "system").mkdir(parents=True)
        (prompts_dir / "tasks").mkdir(parents=True)
        (prompts_dir / "system" / "ceo_agent.txt").write_text("You are CEO. Task: {task}")
        (prompts_dir / "tasks" / "decompose.txt").write_text("Decompose: {objective}")
        return PromptRegistry(prompts_dir=prompts_dir)

    def test_get_existing(self, registry):
        content = registry.get("system/ceo_agent")
        assert "You are CEO" in content

    def test_get_missing_returns_fallback(self, registry):
        content = registry.get("system/nonexistent_agent")
        assert "nonexistent agent" in content.lower()

    def test_render_with_kwargs(self, registry):
        rendered = registry.render("system/ceo_agent", task="review finances")
        assert "review finances" in rendered

    def test_list_templates(self, registry):
        names = registry.list_templates()
        assert "system/ceo_agent" in names
        assert "tasks/decompose" in names

    def test_list_templates_empty_dir(self, tmp_path):
        from sovereign.registries.prompt_registry import PromptRegistry
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        reg = PromptRegistry(prompts_dir=empty_dir)
        assert reg.list_templates() == []

    def test_list_templates_missing_dir(self, tmp_path):
        from sovereign.registries.prompt_registry import PromptRegistry
        reg = PromptRegistry(prompts_dir=tmp_path / "nonexistent")
        assert reg.list_templates() == []

    def test_cache_hit(self, registry):
        # Second call should hit cache
        registry.get("system/ceo_agent")
        content = registry.get("system/ceo_agent")
        assert "You are CEO" in content


class TestVersionedPromptRegistry:
    @pytest.fixture
    def vregistry(self, tmp_path):
        from sovereign.registries.prompt_registry import VersionedPromptRegistry
        prompts_dir = tmp_path / "prompts"
        (prompts_dir / "system").mkdir(parents=True)
        (prompts_dir / "system" / "agent.txt").write_text("v1 content")
        versions_path = tmp_path / "versions.json"
        return VersionedPromptRegistry(
            prompts_dir=prompts_dir,
            versions_path=versions_path,
        )

    def test_get_creates_version(self, vregistry):
        content = vregistry.get("system/agent")
        assert content == "v1 content"
        versions = vregistry.list_versions("system/agent")
        assert len(versions) >= 1

    def test_save_version(self, vregistry):
        vregistry.save_version("system/agent", "v2 content")
        versions = vregistry.list_versions("system/agent")
        assert len(versions) >= 1
        assert any(isinstance(v["version"], int) for v in versions)

    def test_save_duplicate_not_added(self, vregistry):
        vregistry.save_version("system/agent", "same content")
        vregistry.save_version("system/agent", "same content")
        versions = vregistry.list_versions("system/agent")
        assert len(versions) == 1

    def test_get_version_latest(self, vregistry):
        vregistry.save_version("system/agent", "first")
        vregistry.save_version("system/agent", "second")
        content = vregistry.get_version("system/agent", idx=-1)
        assert content == "second"

    def test_get_version_older(self, vregistry):
        vregistry.save_version("system/agent", "first")
        vregistry.save_version("system/agent", "second")
        content = vregistry.get_version("system/agent", idx=0)
        assert content == "first"

    def test_diff(self, vregistry):
        vregistry.save_version("system/agent", "line one\n")
        vregistry.save_version("system/agent", "line two\n")
        diff = vregistry.diff("system/agent", 0, 1)
        assert isinstance(diff, str)

    def test_diff_single_version(self, vregistry):
        vregistry.save_version("system/agent", "only one")
        result = vregistry.diff("system/agent")
        assert "not enough" in result.lower()

    def test_persistence(self, tmp_path):
        from sovereign.registries.prompt_registry import VersionedPromptRegistry
        prompts_dir = tmp_path / "prompts"
        (prompts_dir / "system").mkdir(parents=True)
        (prompts_dir / "system" / "p.txt").write_text("hello")
        versions_path = tmp_path / "v.json"
        r1 = VersionedPromptRegistry(prompts_dir=prompts_dir, versions_path=versions_path)
        r1.get("system/p")
        r2 = VersionedPromptRegistry(prompts_dir=prompts_dir, versions_path=versions_path)
        assert len(r2.list_versions("system/p")) >= 1


# ===========================================================================
# IncidentRegistry
# ===========================================================================

class TestIncidentRegistry:
    @pytest.fixture
    def registry(self, tmp_path):
        from sovereign.registries.incident_registry import IncidentRegistry
        return IncidentRegistry(data_path=tmp_path / "incidents.jsonl")

    def _make_incident(self, title="Test incident"):
        from sovereign.registries.incident_registry import Incident
        import uuid
        return Incident(
            incident_id=str(uuid.uuid4())[:8],
            severity="medium",
            category="agent_failure",
            title=title,
            description="Something went wrong",
        )

    def test_record_incident(self, registry):
        inc = self._make_incident()
        registry.record(inc)
        stats = registry.stats()
        assert stats["total"] >= 1

    def test_recent_includes_incident(self, registry):
        inc = self._make_incident("Find me")
        registry.record(inc)
        recent = registry.recent(limit=10)
        assert any(i.incident_id == inc.incident_id for i in recent)

    def test_resolve_incident(self, registry):
        inc = self._make_incident()
        registry.record(inc)
        ok = registry.resolve(inc.incident_id, notes="Fixed it")
        assert ok is True
        # After resolve, should not appear in open_incidents
        open_list = registry.open_incidents()
        assert not any(i.incident_id == inc.incident_id for i in open_list)

    def test_resolve_nonexistent(self, registry):
        ok = registry.resolve("nonexistent", notes="nothing")
        assert ok is False

    def test_open_incidents(self, registry):
        inc1 = self._make_incident("Open 1")
        inc2 = self._make_incident("Open 2")
        registry.record(inc1)
        registry.record(inc2)
        registry.resolve(inc1.incident_id, "done")
        open_incidents = registry.open_incidents()
        assert len(open_incidents) == 1
        assert open_incidents[0].title == "Open 2"

    def test_open_incidents_by_severity(self, registry):
        from sovereign.registries.incident_registry import Incident
        inc = Incident(
            incident_id="crit-001", severity="critical",
            category="security", title="Breach", description="critical event",
        )
        registry.record(inc)
        critical = registry.open_incidents(severity="critical")
        assert len(critical) >= 1

    def test_by_category(self, registry):
        inc = self._make_incident()
        registry.record(inc)
        results = registry.by_category("agent_failure")
        assert len(results) >= 1

    def test_by_agent(self, registry):
        from sovereign.registries.incident_registry import Incident
        inc = Incident(
            incident_id="a-001", severity="low",
            category="tool_error", title="Tool fail",
            description="desc", agent_id="worker_agent",
        )
        registry.record(inc)
        results = registry.by_agent("worker_agent")
        assert len(results) >= 1

    def test_stats(self, registry):
        registry.record(self._make_incident("Test"))
        s = registry.stats()
        assert "total" in s
        assert s["total"] >= 1

    def test_persistence(self, tmp_path):
        from sovereign.registries.incident_registry import IncidentRegistry
        path = tmp_path / "inc.jsonl"
        r1 = IncidentRegistry(data_path=path)
        r1.record(self._make_incident("Persistent"))
        r2 = IncidentRegistry(data_path=path)
        stats = r2.stats()
        assert stats["total"] >= 1


# ===========================================================================
# WorkflowRegistry
# ===========================================================================

class TestWorkflowRegistry:
    @pytest.fixture
    def registry(self):
        from sovereign.registries.workflow_registry import WorkflowRegistry
        return WorkflowRegistry()

    def _make_wf(self, name="my_workflow"):
        from sovereign.registries.workflow_registry import WorkflowDefinition, WorkflowStep
        return WorkflowDefinition(
            name=name,
            description="Test workflow",
            steps=[
                WorkflowStep(agent_id="research", objective_template="Research {topic}"),
                WorkflowStep(agent_id="worker", objective_template="Summarize: {prev_result}"),
            ],
        )

    def test_register_workflow(self, registry):
        wf = self._make_wf()
        registry.register(wf)
        assert registry.get("my_workflow") is not None

    def test_get_nonexistent_raises(self, registry):
        with pytest.raises((KeyError, ValueError)):
            registry.get("ghost")

    def test_list_workflows(self, registry):
        registry.register(self._make_wf("wf1"))
        registry.register(self._make_wf("wf2"))
        names = registry.list_workflows()
        assert "wf1" in names and "wf2" in names

    def test_workflow_steps(self, registry):
        wf = self._make_wf()
        registry.register(wf)
        fetched = registry.get("my_workflow")
        assert len(fetched.steps) == 2
        assert fetched.steps[0].agent_id == "research"

    def test_register_overwrites(self, registry):
        registry.register(self._make_wf("wf1"))
        wf2 = self._make_wf("wf1")
        wf2.description = "Updated"
        registry.register(wf2)
        assert registry.get("wf1").description == "Updated"


# ===========================================================================
# ModelRouter — enhanced multi-provider features
# ===========================================================================

class TestModelRouterFallback:
    @pytest.fixture
    def router(self):
        from sovereign.router.model_router import ModelRouter
        return ModelRouter()

    def test_route_with_fallback_healthy(self, router):
        from sovereign.router.model_router import RoutingCriteria
        provider, model, chain = router.route_with_fallback(RoutingCriteria())
        assert provider == "anthropic"
        assert isinstance(chain, list)
        assert len(chain) >= 1

    def test_route_with_fallback_high_complexity(self, router):
        from sovereign.router.model_router import RoutingCriteria
        provider, model, _ = router.route_with_fallback(RoutingCriteria(task_complexity=0.95))
        assert model == "claude-opus-4-6"

    def test_pii_stays_on_anthropic(self, router):
        from sovereign.router.model_router import RoutingCriteria
        provider, model, _ = router.route_with_fallback(
            RoutingCriteria(contains_pii=True, preferred_provider="openai")
        )
        assert provider == "anthropic"

    def test_pii_fallback_chain_no_third_party(self, router):
        from sovereign.router.model_router import build_fallback_chain
        chain = build_fallback_chain("anthropic", "claude-sonnet-4-6", contains_pii=True)
        providers = [p for p, _ in chain]
        assert "openai" not in providers
        assert "gemini" not in providers

    def test_caveman_mode_when_all_down(self, router):
        from sovereign.router.model_router import RoutingCriteria
        for provider in ["anthropic", "openai", "gemini", "perplexity", "qwen"]:
            for _ in range(5):
                router.health.record_error(provider)
        provider, model, _ = router.route_with_fallback(RoutingCriteria())
        assert provider == "local"

    def test_openai_preferred(self, router):
        from sovereign.router.model_router import RoutingCriteria
        provider, model, _ = router.route_with_fallback(
            RoutingCriteria(preferred_provider="openai", task_complexity=0.4)
        )
        assert provider == "openai"

    def test_gemini_preferred(self, router):
        from sovereign.router.model_router import RoutingCriteria
        provider, model, _ = router.route_with_fallback(
            RoutingCriteria(preferred_provider="gemini", task_complexity=0.4)
        )
        assert provider == "gemini"

    def test_ultra_low_budget_openai_mini(self, router):
        from sovereign.router.model_router import RoutingCriteria
        provider, model, _ = router.route_with_fallback(
            RoutingCriteria(budget_limit_usd=0.0001)
        )
        assert provider == "openai"
        assert model == "gpt-4o-mini"

    def test_tight_latency_local(self, router):
        from sovereign.router.model_router import RoutingCriteria
        provider, model, _ = router.route_with_fallback(
            RoutingCriteria(latency_budget_ms=200, preferred_provider="anthropic")
        )
        assert provider == "local"


class TestProviderHealth:
    @pytest.fixture
    def tracker(self):
        from sovereign.router.model_router import ProviderHealthTracker
        return ProviderHealthTracker()

    def test_all_healthy_initially(self, tracker):
        assert tracker.is_healthy("anthropic")
        assert tracker.is_healthy("openai")

    def test_record_error_increments(self, tracker):
        tracker.record_error("anthropic")
        assert tracker.get("anthropic").error_count == 1

    def test_circuit_opens_after_threshold(self, tracker):
        for _ in range(3):
            tracker.record_error("openai")
        assert not tracker.is_healthy("openai")

    def test_record_success_updates_latency(self, tracker):
        tracker.record_success("anthropic", latency_ms=500.0)
        assert tracker.get("anthropic").latency_p50_ms > 0

    def test_healthy_providers_excludes_down(self, tracker):
        for _ in range(3):
            tracker.record_error("openai")
        healthy = tracker.healthy_providers()
        assert "openai" not in healthy
        assert "anthropic" in healthy

    def test_report_structure(self, tracker):
        report = tracker.report()
        assert "anthropic" in report
        assert "available" in report["anthropic"]

    def test_new_provider_auto_registered(self, tracker):
        tracker.record_error("new_provider")
        assert tracker.get("new_provider") is not None


class TestBuildFallbackChain:
    def test_standard_chain_order(self):
        from sovereign.router.model_router import build_fallback_chain
        chain = build_fallback_chain("anthropic", "claude-sonnet-4-6")
        providers = [p for p, _ in chain]
        assert providers[0] == "anthropic"
        assert "local" in providers

    def test_offline_only_chain(self):
        from sovereign.router.model_router import build_fallback_chain
        chain = build_fallback_chain("anthropic", "claude-sonnet-4-6", offline_only=True)
        assert len(chain) == 1
        assert chain[0][0] == "local"

    def test_pii_chain_safe(self):
        from sovereign.router.model_router import build_fallback_chain
        chain = build_fallback_chain("anthropic", "claude-sonnet-4-6", contains_pii=True)
        third_party = {"openai", "gemini", "perplexity"}
        providers = {p for p, _ in chain}
        assert providers.isdisjoint(third_party)

    def test_no_duplicate_entries(self):
        from sovereign.router.model_router import build_fallback_chain
        chain = build_fallback_chain("anthropic", "claude-sonnet-4-6")
        assert len(chain) == len(set(chain))
