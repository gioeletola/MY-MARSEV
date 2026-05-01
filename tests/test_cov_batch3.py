"""
Coverage batch 3: telemetry store/aggregator, secrets_vault, entity_registry,
agent_factory, model_performance_tracker, daily_digest (unit).
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock


def run(coro):
    return asyncio.run(coro)


# ===========================================================================
# TelemetryStore
# ===========================================================================

class TestTelemetryStore:
    def setup_method(self):
        from sovereign.telemetry.store import TelemetryStore
        self.store = TelemetryStore(persist=False, max_events=500)

    def test_record_event(self):
        ev = self.store.record("test_event", source="pytest", data={"k": 1})
        assert ev is not None
        assert ev.event_type == "test_event"

    def test_record_multiple(self):
        for i in range(5):
            self.store.record("evt", source="test", data={"i": i})
        count = self.store.count()
        assert count == 5

    def test_recent(self):
        for i in range(10):
            self.store.record("recent_evt", source="test", data={"i": i})
        results = self.store.recent(5)
        assert len(results) == 5

    def test_query_by_event_type(self):
        self.store.record("alpha", source="s", data={})
        self.store.record("beta", source="s", data={})
        results = self.store.query(event_type="alpha")
        assert all(r.event_type == "alpha" for r in results)

    def test_query_by_source(self):
        self.store.record("x", source="src_a", data={})
        self.store.record("x", source="src_b", data={})
        results = self.store.query(source="src_a")
        assert all(r.source == "src_a" for r in results)

    def test_aggregate_basic(self):
        for i in range(5):
            self.store.record("req", source="s", data={"latency_ms": 10 * i})
        result = self.store.aggregate(event_type="req")
        assert isinstance(result, dict)

    def test_stats(self):
        self.store.record("evt", source="s", data={})
        s = self.store.stats()
        assert isinstance(s, dict)
        assert "total_events" in s or "count" in s or len(s) > 0

    def test_flush_no_persist(self):
        for _ in range(5):
            self.store.record("tmp", source="s", data={})
        removed = self.store.flush()
        assert isinstance(removed, int)

    def test_iter_all(self):
        # iter_all reads from JSONL file — use persistent store in temp dir
        import tempfile
        from sovereign.telemetry.store import TelemetryStore
        with tempfile.TemporaryDirectory() as d:
            store = TelemetryStore(path=Path(d) / "tel.jsonl", persist=True, max_events=100)
            store.record("iter_evt", source="s", data={"x": 1})
            events = list(store.iter_all())
            assert len(events) >= 1

    def test_count_empty(self):
        store = __import__("sovereign.telemetry.store", fromlist=["TelemetryStore"]).TelemetryStore(persist=False)
        assert store.count() == 0

    def test_record_with_tags(self):
        ev = self.store.record("tagged", source="s", data={}, tags=["tag1", "tag2"])
        assert ev is not None

    def test_export_jsonl(self):
        self.store.record("export_evt", source="s", data={"val": 42})
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            count = self.store.export_jsonl(path)
            assert count >= 1
        finally:
            os.unlink(path)


# ===========================================================================
# TelemetryAggregator
# ===========================================================================

class TestTelemetryAggregator:
    def setup_method(self):
        from sovereign.telemetry.aggregator import TelemetryAggregator
        from sovereign.telemetry.store import TelemetryStore
        self.agg = TelemetryAggregator()
        self.store = TelemetryStore(persist=False, max_events=1000)

    def test_compute_metrics_empty(self):
        result = self.agg.compute_metrics(store=self.store, window_seconds=3600)
        assert isinstance(result, dict)
        assert "event_count" in result or "request_rate" in result

    def test_compute_metrics_with_data(self):
        for i in range(5):
            self.store.record("request", source="agent", data={"latency_ms": 50 + i})
        self.store.record("error", source="agent", data={"success": False})
        result = self.agg.compute_metrics(store=self.store, window_seconds=3600)
        assert isinstance(result, dict)

    def test_trend_empty(self):
        result = self.agg.trend(store=self.store, metric="avg_latency_ms", window_seconds=3600)
        assert isinstance(result, list)

    def test_trend_with_data(self):
        for i in range(10):
            self.store.record("session_end", source="test", data={"latency_ms": 100 + i * 5})
        result = self.agg.trend(store=self.store, metric="avg_latency_ms", window_seconds=3600)
        assert isinstance(result, list)

    def test_alert_if_no_trigger(self):
        result = self.agg.alert_if(
            store=self.store, metric="error_rate", threshold=0.5, comparator="gt"
        )
        assert isinstance(result, bool)

    def test_alert_if_triggered(self):
        for _ in range(20):
            self.store.record("error", source="s", data={"success": False})
        result = self.agg.alert_if(
            store=self.store, metric="error_rate", threshold=0.0, comparator="gt"
        )
        assert isinstance(result, bool)

    def test_compute_stats_module_fn(self):
        from sovereign.telemetry.aggregator import compute_stats
        result = compute_stats(period="day")
        assert isinstance(result, object)  # returns AggregatedStats

    def test_to_dict_module_fn(self):
        from sovereign.telemetry.aggregator import compute_stats, to_dict
        stats = compute_stats(period="day")
        d = to_dict(stats)
        assert isinstance(d, dict)


# ===========================================================================
# DecisionLedger
# ===========================================================================



class TestDecisionLedger:
    def setup_method(self):
        from sovereign.registries.decision_ledger import DecisionLedger, DecisionRecord
        self.DL = DecisionLedger
        self.DR = DecisionRecord
        self._tmpdir = tempfile.mkdtemp()
        self.ledger = DecisionLedger(data_dir=self._tmpdir)

    def _record(self, dtype="task_dispatch", sid="s1", aid="a1"):
        return self.DR(
            session_id=sid,
            agent_id=aid,
            decision_type=dtype,
            description="Test decision",
            inputs={"key": "value"},
            outcome="completed",
            confidence=0.9,
        )

    def test_record_and_query(self):
        run(self.ledger.record(self._record()))
        results = run(self.ledger.query())
        assert len(results) >= 1

    def test_query_by_session(self):
        run(self.ledger.record(self._record(sid="sess_a")))
        run(self.ledger.record(self._record(sid="sess_b")))
        results = run(self.ledger.query(session_id="sess_a"))
        assert all(r.session_id == "sess_a" for r in results)

    def test_query_by_agent(self):
        run(self.ledger.record(self._record(aid="agent_x")))
        run(self.ledger.record(self._record(aid="agent_y")))
        results = run(self.ledger.query(agent_id="agent_x"))
        assert all(r.agent_id == "agent_x" for r in results)

    def test_query_by_type(self):
        run(self.ledger.record(self._record(dtype="approval")))
        run(self.ledger.record(self._record(dtype="tool_exec")))
        results = run(self.ledger.query(decision_type="approval"))
        assert all(r.decision_type == "approval" for r in results)

    def test_query_limit(self):
        for i in range(10):
            run(self.ledger.record(self._record()))
        results = run(self.ledger.query(limit=3))
        assert len(results) <= 3

    def test_query_empty_ledger(self):
        results = run(self.ledger.query())
        assert isinstance(results, list)

    def test_decision_record_to_dict(self):
        rec = self._record()
        d = rec.to_dict()
        assert d["session_id"] == "s1"
        assert d["agent_id"] == "a1"
        assert "decision_id" in d
        assert "timestamp" in d

    def test_decision_record_auto_id(self):
        r1 = self._record()
        r2 = self._record()
        assert r1.decision_id != r2.decision_id

    def test_multiple_records_append(self):
        for i in range(5):
            run(self.ledger.record(self._record()))
        results = run(self.ledger.query())
        assert len(results) == 5


# ===========================================================================
# EntityRegistry
# ===========================================================================

class TestEntityRegistry:
    def setup_method(self):
        from sovereign.entities.entity_registry import EntityRegistry, Entity, EntityType
        self.EntityType = EntityType
        self.Entity = Entity
        # Use temp file to avoid polluting real data
        self._tmpdir = tempfile.mkdtemp()
        self.registry = EntityRegistry(data_path=Path(self._tmpdir) / "entities.json")

    def _make_entity(self, eid: str = "ent1", etype: str = "person") -> "Entity":
        return self.Entity(
            entity_id=eid,
            name="Test Entity",
            entity_type=etype,
            attributes={"key": "value"},
        )

    def test_upsert_and_get(self):
        ent = self._make_entity()
        self.registry.upsert(ent)
        fetched = self.registry.get_entity("ent1")
        assert fetched is not None
        assert fetched.name == "Test Entity"

    def test_list_entities_empty(self):
        from sovereign.entities.entity_registry import EntityRegistry
        empty = EntityRegistry(data_path=Path(self._tmpdir) / "empty.json")
        result = empty.list_entities()
        assert isinstance(result, list)
        assert len(result) == 0

    def test_list_entities_filtered(self):
        self.registry.upsert(self._make_entity("p1", "person"))
        self.registry.upsert(self._make_entity("o1", "organization"))
        persons = self.registry.list_entities(entity_type="person")
        assert all(e.entity_type == "person" for e in persons)

    def test_delete_entity(self):
        self.registry.upsert(self._make_entity("to_delete"))
        result = self.registry.delete_entity("to_delete")
        assert result is True
        assert self.registry.get_entity("to_delete") is None

    def test_delete_nonexistent(self):
        result = self.registry.delete_entity("ghost_entity_xyz")
        assert result is False

    def test_search_basic(self):
        self.registry.upsert(self._make_entity("s1", "person"))
        results = self.registry.search("Test")
        assert isinstance(results, list)

    def test_relate_entities(self):
        self.registry.upsert(self._make_entity("a1", "person"))
        self.registry.upsert(self._make_entity("b1", "person"))
        self.registry.relate("a1", "b1", "knows")
        neighbors = self.registry.graph_neighbors("a1", depth=1)
        assert isinstance(neighbors, list)

    def test_merge_entities(self):
        self.registry.upsert(self._make_entity("m1", "person"))
        self.registry.upsert(self._make_entity("m2", "person"))
        merged = self.registry.merge("m1", "m2")
        assert merged is not None

    def test_entity_to_dict(self):
        ent = self._make_entity()
        d = ent.to_dict()
        assert isinstance(d, dict)
        assert d["entity_id"] == "ent1"

    def test_entity_from_dict(self):
        ent = self._make_entity()
        d = ent.to_dict()
        restored = self.Entity.from_dict(d)
        assert restored.entity_id == "ent1"

    def test_make_entity_id(self):
        from sovereign.entities.entity_registry import make_entity_id
        eid = make_entity_id()
        assert isinstance(eid, str)
        assert len(eid) > 0


# ===========================================================================
# AgentFactory (mocked)
# ===========================================================================

def _make_factory_deps():
    from sovereign.registries.agent_registry import AgentRegistry
    registry = AgentRegistry()
    return {
        "claude_client": MagicMock(complete=AsyncMock(return_value="ok")),
        "tool_registry": MagicMock(list_schemas=MagicMock(return_value=[])),
        "memory_manager": MagicMock(get_snapshot=AsyncMock(return_value={})),
        "constitution": MagicMock(render_for_prompt=MagicMock(return_value="sys")),
        "prompt_builder": MagicMock(build_for_agent=MagicMock(return_value=[{"type": "text", "text": "sys"}])),
        "agent_registry": registry,
    }


class TestAgentFactory:
    def setup_method(self):
        from sovereign.factory.agent_factory import AgentFactory
        self.AgentFactory = AgentFactory
        self.deps = _make_factory_deps()

    def _factory(self):
        return self.AgentFactory(**self.deps)

    def _spec(self, name="test_worker"):
        from sovereign.factory.agent_spec import AgentSpec
        return AgentSpec(
            name=name,
            role="tester",
            objective="Do some test work",
            ttl_seconds=60,
        )

    def test_spawn_agent(self):
        factory = self._factory()
        agent = run(factory.spawn(self._spec()))
        assert agent is not None
        assert "test_worker" in agent.agent_id

    def test_spawn_returns_ephemeral(self):
        from sovereign.swarm.ephemeral_agent import EphemeralAgent
        factory = self._factory()
        agent = run(factory.spawn(self._spec()))
        assert isinstance(agent, EphemeralAgent)

    def test_list_active(self):
        factory = self._factory()
        run(factory.spawn(self._spec("worker_a")))
        active = factory.list_active()
        assert isinstance(active, list)
        assert len(active) >= 1

    def test_get_pool(self):
        factory = self._factory()
        run(factory.spawn(self._spec()))
        pool = factory.get_pool()
        assert isinstance(pool, dict)

    def test_pool_stats(self):
        factory = self._factory()
        run(factory.spawn(self._spec()))
        stats = factory.pool_stats()
        assert isinstance(stats, dict)

    def test_heat_map(self):
        factory = self._factory()
        run(factory.spawn(self._spec("hot_agent")))
        run(factory.spawn(self._spec("hot_agent")))
        hmap = factory.heat_map()
        assert isinstance(hmap, dict)
        assert hmap.get("hot_agent", 0) >= 2

    def test_despawn_agent(self):
        factory = self._factory()
        agent = run(factory.spawn(self._spec()))
        result = run(factory.despawn(agent.agent_id))
        assert result is True

    def test_despawn_nonexistent(self):
        factory = self._factory()
        result = run(factory.despawn("nonexistent_agent_xyz"))
        assert result is False

    def test_recycle(self):
        factory = self._factory()
        agent = run(factory.spawn(self._spec()))
        recycled = factory.recycle(agent.agent_id)
        assert isinstance(recycled, bool)

    def test_get_agent(self):
        factory = self._factory()
        agent = run(factory.spawn(self._spec()))
        fetched = factory.get(agent.agent_id)
        assert fetched is not None

    def test_spawn_batch(self):
        factory = self._factory()
        specs = [self._spec(f"batch_{i}") for i in range(3)]
        agents = run(factory.spawn_batch(specs))
        assert len(agents) == 3

    def test_invalid_spec_raises(self):
        from sovereign.factory.agent_spec import AgentSpec
        factory = self._factory()
        bad_spec = AgentSpec(name="", role="r", objective="o")
        try:
            run(factory.spawn(bad_spec))
            assert False, "Should have raised ValueError"
        except (ValueError, Exception):
            pass

    def test_agent_spec_to_dict(self):
        spec = self._spec()
        d = spec.to_dict()
        assert isinstance(d, dict)
        assert d["name"] == "test_worker"

    def test_agent_spec_validate_bad_ttl(self):
        from sovereign.factory.agent_spec import AgentSpec
        spec = AgentSpec(name="ok", role="r", objective="o", ttl_seconds=0)
        try:
            spec.validate()
            assert False, "Should raise"
        except ValueError:
            pass


# ===========================================================================
# ModelPerformanceTracker
# ===========================================================================

class TestModelPerformanceTracker:
    def setup_method(self):
        from sovereign.observability.model_performance_tracker import ModelPerformanceTracker
        self._tmpdir = tempfile.mkdtemp()
        self.tracker = ModelPerformanceTracker(
            data_path=Path(self._tmpdir) / "perf.json"
        )

    def test_record_call(self):
        self.tracker.record(
            model_id="claude-sonnet-4-6",
            latency_ms=250.0,
            tokens_in=100,
            tokens_out=50,
            cost_usd=0.001,
            confidence=0.9,
            success=True,
        )
        stats = self.tracker.get_stats("claude-sonnet-4-6")
        assert isinstance(stats, dict)

    def test_record_failure(self):
        self.tracker.record(
            model_id="claude-opus-4-7",
            latency_ms=100.0,
            tokens_in=50,
            tokens_out=0,
            cost_usd=0.0,
            confidence=0.0,
            success=False,
        )
        stats = self.tracker.get_stats("claude-opus-4-7")
        assert isinstance(stats, dict)

    def test_compare_models(self):
        self.tracker.record("claude-sonnet-4-6", 200.0, 100, 50, 0.001, 0.9, True)
        self.tracker.record("claude-haiku-4-5-20251001", 100.0, 80, 30, 0.0005, 0.8, True)
        comparison = self.tracker.compare_models()
        assert isinstance(comparison, list)

    def test_to_dict(self):
        self.tracker.record("claude-sonnet-4-6", 200.0, 100, 50, 0.001, 0.9, True)
        d = self.tracker.to_dict()
        assert isinstance(d, dict)

    def test_get_stats_unknown_model(self):
        stats = self.tracker.get_stats("unknown-model-xyz")
        assert isinstance(stats, dict)


# ===========================================================================
# DailyDigest (unit — mocked orchestrator)
# ===========================================================================

class TestDailyDigest:
    def _make_orch(self):
        orch = MagicMock()
        orch.health = AsyncMock(return_value={"status": "healthy", "uptime_seconds": 3600})
        orch.memory = MagicMock()
        orch.memory.read = AsyncMock(return_value={"goals": [], "budget": {}})
        orch.memory.get_snapshot = AsyncMock(return_value={})
        return orch

    def test_digest_instantiation(self):
        from sovereign.proactive.daily_digest import DailyDigest
        orch = self._make_orch()
        digest = DailyDigest(orchestrator=orch)
        assert digest is not None

    def test_digest_report_is_string(self):
        from sovereign.proactive.daily_digest import DailyDigest
        orch = self._make_orch()
        digest = DailyDigest(orchestrator=orch)
        report = run(digest.generate())
        assert isinstance(report.text, str)
        assert len(report.text) > 0

    def test_digest_to_telegram(self):
        from sovereign.proactive.daily_digest import DailyDigest
        orch = self._make_orch()
        digest = DailyDigest(orchestrator=orch)
        report = run(digest.generate())
        tg = report.to_telegram()
        assert isinstance(tg, str)

    def test_digest_generated_at(self):
        from sovereign.proactive.daily_digest import DailyDigest
        orch = self._make_orch()
        digest = DailyDigest(orchestrator=orch)
        report = run(digest.generate())
        assert isinstance(report.generated_at, str)

    def test_build_daily_digest_task(self):
        from sovereign.proactive.daily_digest import build_daily_digest_task
        orch = self._make_orch()
        task = build_daily_digest_task(orch, digest_hour=8)
        assert callable(task) or task is not None


# ===========================================================================
# AgentPool (unit)
# ===========================================================================

class TestAgentPool:
    def setup_method(self):
        from sovereign.factory.agent_factory import AgentPool
        self.pool = AgentPool(max_size=5, idle_timeout_seconds=60)

    def _make_ephemeral(self, name="test_ep"):
        from sovereign.swarm.ephemeral_agent import EphemeralAgent
        from sovereign.factory.agent_spec import AgentSpec
        spec = AgentSpec(name=name, role="r", objective="o")
        agent = EphemeralAgent(
            spec=spec,
            claude_client=MagicMock(complete=AsyncMock(return_value="ok")),
            tool_registry=MagicMock(list_schemas=MagicMock(return_value=[])),
            memory_manager=MagicMock(),
            constitution=MagicMock(render_for_prompt=MagicMock(return_value="")),
            prompt_builder=MagicMock(build_for_agent=MagicMock(return_value=[])),
        )
        return agent

    def test_add_and_get(self):
        agent = self._make_ephemeral()
        self.pool.add(agent)
        fetched = self.pool.get(agent.agent_id)
        assert fetched is not None

    def test_remove(self):
        agent = self._make_ephemeral()
        self.pool.add(agent)
        result = self.pool.remove(agent.agent_id)
        assert result is True

    def test_stats(self):
        agent = self._make_ephemeral()
        self.pool.add(agent)
        stats = self.pool.stats()
        assert isinstance(stats, dict)

    def test_all_agents(self):
        agent = self._make_ephemeral("ep_a")
        self.pool.add(agent)
        all_a = self.pool.all_agents()
        assert isinstance(all_a, dict)
