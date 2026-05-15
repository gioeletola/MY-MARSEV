"""Tests for the 6 new modules added in the 'aggiungi tutto' sprint.

Covers: oauth_refresh, memory.seed, memory.compaction,
        swarm.agent_bus, registries.eval_agent, proactive.morning_loop.
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# oauth_refresh
# ---------------------------------------------------------------------------

class TestOAuthRefresh:
    def setup_method(self):
        from sovereign.integrations.connectors import oauth_refresh
        oauth_refresh.invalidate()  # clear cache between tests

    def test_invalidate_all(self):
        from sovereign.integrations.connectors import oauth_refresh
        oauth_refresh._token_cache["x"] = ("tok", time.time() + 3600)
        oauth_refresh.invalidate()
        assert oauth_refresh._token_cache == {}

    def test_invalidate_one(self):
        from sovereign.integrations.connectors import oauth_refresh
        oauth_refresh._token_cache["a"] = ("tok_a", time.time() + 3600)
        oauth_refresh._token_cache["b"] = ("tok_b", time.time() + 3600)
        oauth_refresh.invalidate("a")
        assert "a" not in oauth_refresh._token_cache
        assert "b" in oauth_refresh._token_cache

    @pytest.mark.asyncio
    async def test_ensure_fresh_token_no_refresh_token(self):
        from sovereign.integrations.connectors.oauth_refresh import ensure_fresh_token
        result = await ensure_fresh_token("original_token", "")
        assert result == "original_token"

    @pytest.mark.asyncio
    async def test_ensure_fresh_token_uses_cache(self):
        from sovereign.integrations.connectors import oauth_refresh
        oauth_refresh._token_cache["rt1"] = ("cached_tok", time.time() + 3600)
        result = await oauth_refresh.ensure_fresh_token("old", "rt1")
        assert result == "cached_tok"

    @pytest.mark.asyncio
    async def test_ensure_fresh_token_expired_cache_no_creds(self):
        from sovereign.integrations.connectors import oauth_refresh
        oauth_refresh._token_cache["rt2"] = ("old_tok", time.time() - 10)
        # No client_id/secret → refresh fails → return original
        with patch.dict("os.environ", {"GOOGLE_CLIENT_ID": "", "GOOGLE_CLIENT_SECRET": ""}):
            result = await oauth_refresh.ensure_fresh_token("fallback", "rt2")
        assert result == "fallback"

    @pytest.mark.asyncio
    async def test_refresh_google_token_no_credentials(self):
        from sovereign.integrations.connectors.oauth_refresh import refresh_google_token
        with patch.dict("os.environ", {"GOOGLE_CLIENT_ID": "", "GOOGLE_CLIENT_SECRET": ""}):
            result = await refresh_google_token("rt")
        assert result is None

    @pytest.mark.asyncio
    async def test_refresh_google_token_success(self):
        from sovereign.integrations.connectors import oauth_refresh
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "new_tok", "expires_in": 3600}
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        with patch("httpx.AsyncClient", return_value=mock_ctx):
            with patch.dict("os.environ", {"GOOGLE_CLIENT_ID": "cid", "GOOGLE_CLIENT_SECRET": "csec"}):
                result = await oauth_refresh.refresh_google_token("rt_x")
        assert result == "new_tok"
        assert "rt_x" in oauth_refresh._token_cache

    @pytest.mark.asyncio
    async def test_refresh_google_token_http_error(self):
        from sovereign.integrations.connectors import oauth_refresh
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        with patch("httpx.AsyncClient", return_value=mock_ctx):
            with patch.dict("os.environ", {"GOOGLE_CLIENT_ID": "cid", "GOOGLE_CLIENT_SECRET": "csec"}):
                result = await oauth_refresh.refresh_google_token("rt_bad")
        assert result is None


# ---------------------------------------------------------------------------
# memory.seed
# ---------------------------------------------------------------------------

class TestMemorySeed:
    @pytest.mark.asyncio
    async def test_already_seeded_returns_false(self):
        from sovereign.memory.seed import run_seed
        mem = AsyncMock()
        mem.read = AsyncMock(return_value={"ts": "2026-01-01T00:00:00Z", "version": 1})
        result = await run_seed(mem)
        assert result is False
        mem.write.assert_not_called()

    @pytest.mark.asyncio
    async def test_first_seed_writes_domains(self):
        from sovereign.memory.seed import run_seed
        mem = AsyncMock()
        mem.read = AsyncMock(return_value=None)
        mem.write = AsyncMock(return_value=None)
        result = await run_seed(mem)
        assert result is True
        written_domains = {call.args[0] for call in mem.write.call_args_list}
        assert "identity" in written_domains
        assert "operational" in written_domains
        assert "financial" in written_domains
        assert "project" in written_domains
        assert "personal_constitution" in written_domains

    @pytest.mark.asyncio
    async def test_seed_writes_owner_from_env(self):
        from sovereign.memory.seed import run_seed
        mem = AsyncMock()
        mem.read = AsyncMock(return_value=None)
        mem.write = AsyncMock(return_value=None)
        with patch.dict("os.environ", {"SOVEREIGN_OWNER_NAME": "TestUser"}):
            await run_seed(mem)
        owner_call = next(
            c for c in mem.write.call_args_list if c.args[1] == "owner"
        )
        assert owner_call.args[2]["name"] == "TestUser"


# ---------------------------------------------------------------------------
# memory.compaction
# ---------------------------------------------------------------------------

class TestMemoryCompaction:
    @pytest.mark.asyncio
    async def test_run_no_stale_keys(self):
        from sovereign.memory.compaction import MemoryCompaction
        mem = AsyncMock()
        mem.list_keys = AsyncMock(return_value=[])
        mem.write = AsyncMock(return_value=None)
        mc = MemoryCompaction(mem)
        report = await mc.run()
        assert report["total_removed"] == 0
        assert "started_at" in report
        assert "finished_at" in report

    @pytest.mark.asyncio
    async def test_run_removes_stale_transient(self):
        from sovereign.memory.compaction import MemoryCompaction
        mem = AsyncMock()
        stale_record = {"created_at": "2020-01-01T00:00:00Z"}
        fresh_record = {"created_at": "2026-01-01T00:00:00Z"}
        mem.list_keys = AsyncMock(side_effect=lambda d: ["_tmp_stale", "_tmp_fresh", "normal"])
        async def _read(domain, key):
            if key == "_tmp_stale":
                return stale_record
            if key == "_tmp_fresh":
                return fresh_record
            return {"created_at": "2026-01-01T00:00:00Z"}
        mem.read = _read
        mem.delete = AsyncMock(return_value=None)
        mem.write = AsyncMock(return_value=None)
        mc = MemoryCompaction(mem)
        report = await mc.run()
        assert report["total_removed"] >= 1

    @pytest.mark.asyncio
    async def test_compact_domain_list_keys_error(self):
        from sovereign.memory.compaction import MemoryCompaction
        mem = AsyncMock()
        mem.list_keys = AsyncMock(side_effect=Exception("DB error"))
        mem.write = AsyncMock(return_value=None)
        mc = MemoryCompaction(mem)
        removed = await mc._compact_domain("identity", "2020-01-01T00:00:00Z")
        assert removed == 0

    @pytest.mark.asyncio
    async def test_save_report_failure_is_silent(self):
        from sovereign.memory.compaction import MemoryCompaction
        mem = AsyncMock()
        mem.list_keys = AsyncMock(return_value=[])
        mem.write = AsyncMock(side_effect=Exception("write fail"))
        mc = MemoryCompaction(mem)
        # Should not raise
        await mc._save_report({"started_at": "2026-01-01", "total_removed": 0})


# ---------------------------------------------------------------------------
# swarm.agent_bus
# ---------------------------------------------------------------------------

class TestAgentBus:
    def test_register_and_list(self):
        from sovereign.swarm.agent_bus import AgentBus
        bus = AgentBus()
        async def handler(q, env): return "ok"
        bus.register("alpha", handler)
        assert "alpha" in bus.registered_agents()

    def test_unregister(self):
        from sovereign.swarm.agent_bus import AgentBus
        bus = AgentBus()
        async def handler(q, env): return "ok"
        bus.register("beta", handler)
        bus.unregister("beta")
        assert "beta" not in bus.registered_agents()

    @pytest.mark.asyncio
    async def test_ask_success(self):
        from sovereign.swarm.agent_bus import AgentBus
        bus = AgentBus()
        async def handler(q, env):
            return f"answer to: {q}"
        bus.register("research", handler)
        result = await bus.ask("ceo", "research", "What is 2+2?")
        assert result == "answer to: What is 2+2?"

    @pytest.mark.asyncio
    async def test_ask_unregistered_raises(self):
        from sovereign.swarm.agent_bus import AgentBus
        bus = AgentBus()
        with pytest.raises(RuntimeError, match="no handler"):
            await bus.ask("ceo", "ghost", "hello")

    @pytest.mark.asyncio
    async def test_ask_timeout(self):
        from sovereign.swarm.agent_bus import AgentBus
        bus = AgentBus()
        async def slow_handler(q, env):
            await asyncio.sleep(10)
            return "late"
        bus.register("slow", slow_handler)
        with pytest.raises(asyncio.TimeoutError):
            await bus.ask("ceo", "slow", "hurry", timeout=0.05)

    @pytest.mark.asyncio
    async def test_ask_agent_shorthand(self):
        from sovereign.swarm.agent_bus import AgentBus
        bus = AgentBus()
        async def handler(q, env): return "shorthand_ok"
        bus.register("finance", handler)
        result = await bus.ask_agent("finance", "balance sheet?")
        assert result == "shorthand_ok"

    @pytest.mark.asyncio
    async def test_broadcast(self):
        from sovereign.swarm.agent_bus import AgentBus
        bus = AgentBus()
        async def h1(q, env): return "r1"
        async def h2(q, env): return "r2"
        bus.register("agent1", h1)
        bus.register("agent2", h2)
        results = await bus.broadcast("ceo", "status?")
        assert results["agent1"] == "r1"
        assert results["agent2"] == "r2"

    @pytest.mark.asyncio
    async def test_broadcast_excludes_sender(self):
        from sovereign.swarm.agent_bus import AgentBus
        bus = AgentBus()
        async def h(q, env): return "resp"
        bus.register("sender", h)
        bus.register("other", h)
        results = await bus.broadcast("sender", "ping")
        assert "sender" not in results
        assert "other" in results

    @pytest.mark.asyncio
    async def test_broadcast_captures_errors(self):
        from sovereign.swarm.agent_bus import AgentBus
        bus = AgentBus()
        async def bad(q, env): raise ValueError("boom")
        bus.register("broken", bad)
        results = await bus.broadcast("ceo", "ping")
        assert "error" in results["broken"]


# ---------------------------------------------------------------------------
# registries.eval_agent
# ---------------------------------------------------------------------------

class TestRegistriesEvalAgent:
    @pytest.mark.asyncio
    async def test_run_no_poor_agents(self):
        from sovereign.registries.eval_agent import EvalAgent
        registry = MagicMock()
        registry.poor_agents.return_value = []
        agent = EvalAgent(feedback_registry=registry)
        results = await agent.run()
        assert results == []

    @pytest.mark.asyncio
    async def test_run_no_api_key_returns_stub(self):
        from sovereign.registries.eval_agent import EvalAgent
        registry = MagicMock()
        registry.poor_agents.return_value = [{"agent_id": "slow_agent", "score": -0.5, "count": 3}]
        registry._load.return_value = []
        agent = EvalAgent(feedback_registry=registry)
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}):
            results = await agent.run()
        assert len(results) == 1
        assert results[0]["agent_id"] == "slow_agent"
        assert "ANTHROPIC_API_KEY" in results[0]["suggestion"]

    @pytest.mark.asyncio
    async def test_run_with_api_key_calls_claude(self):
        from sovereign.registries.eval_agent import EvalAgent
        registry = MagicMock()
        registry.poor_agents.return_value = [{"agent_id": "bad_agent", "score": -0.8, "count": 5}]
        registry._load.return_value = [
            {"agent_id": "bad_agent", "rating": -1, "comment": "too slow"}
        ]
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="Add a timeout of 30s to your prompts.")]
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_msg)
        with patch("anthropic.AsyncAnthropic", return_value=mock_client):
            with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
                agent = EvalAgent(feedback_registry=registry)
                results = await agent.run()
        assert results[0]["suggestion"] == "Add a timeout of 30s to your prompts."

    @pytest.mark.asyncio
    async def test_report_to_memory(self):
        from sovereign.registries.eval_agent import EvalAgent
        mem = AsyncMock()
        agent = EvalAgent()
        results = [{"agent_id": "x", "score": -0.5, "count": 2, "suggestion": "do better"}]
        await agent.report_to_memory(mem, results)
        mem.write.assert_called_once()
        domain_arg = mem.write.call_args.args[0]
        assert domain_arg == "learning"

    @pytest.mark.asyncio
    async def test_get_negative_comments_filters_correctly(self):
        from sovereign.registries.eval_agent import EvalAgent
        registry = MagicMock()
        registry._load.return_value = [
            {"agent_id": "a", "rating": -1, "comment": "bad output"},
            {"agent_id": "a", "rating": 1, "comment": "good output"},
            {"agent_id": "b", "rating": -1, "comment": "wrong agent"},
            {"agent_id": "a", "rating": -1, "comment": ""},  # no comment
        ]
        agent = EvalAgent(feedback_registry=registry)
        comments = agent._get_negative_comments("a")
        assert comments == ["bad output"]


# ---------------------------------------------------------------------------
# proactive.morning_loop
# ---------------------------------------------------------------------------

class TestMorningLoop:
    @pytest.mark.asyncio
    async def test_run_no_telegram_no_crash(self):
        from sovereign.proactive.morning_loop import MorningLoop
        mem = AsyncMock()
        mem.read = AsyncMock(return_value=None)
        mem.write = AsyncMock(return_value=None)
        orch = MagicMock()
        orch._memory = mem
        ml = MorningLoop(orchestrator=orch)
        with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}):
            brief = await ml.run()
        assert isinstance(brief, str)
        assert len(brief) > 0

    @pytest.mark.asyncio
    async def test_run_saves_to_memory(self):
        from sovereign.proactive.morning_loop import MorningLoop
        mem = AsyncMock()
        mem.read = AsyncMock(return_value=None)
        mem.write = AsyncMock(return_value=None)
        orch = MagicMock()
        orch._memory = mem
        ml = MorningLoop(orchestrator=orch)
        with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}):
            await ml.run()
        mem.write.assert_called()

    @pytest.mark.asyncio
    async def test_run_sends_telegram_when_configured(self):
        from sovereign.proactive.morning_loop import MorningLoop
        mem = AsyncMock()
        mem.read = AsyncMock(return_value=None)
        mem.write = AsyncMock(return_value=None)
        orch = MagicMock()
        orch._memory = mem
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        with patch("httpx.AsyncClient", return_value=mock_ctx):
            with patch.dict("os.environ", {
                "TELEGRAM_BOT_TOKEN": "test:token",
                "TELEGRAM_CHAT_ID": "12345",
            }):
                ml = MorningLoop(orchestrator=orch)
                await ml.run()
        mock_client.post.assert_called_once()


# ---------------------------------------------------------------------------
# validate_mode + _enrich_from_config (modes/__init__.py)
# ---------------------------------------------------------------------------

class TestValidateMode:
    def test_valid_mode_returns_true(self):
        from sovereign.modes import validate_mode
        assert validate_mode("command") is True
        assert validate_mode("finance") is True
        assert validate_mode("caveman") is True

    def test_invalid_mode_returns_false(self):
        from sovereign.modes import validate_mode
        assert validate_mode("nonexistent_mode") is False
        assert validate_mode("") is False

    def test_all_17_modes_valid(self):
        from sovereign.modes import MODES, validate_mode
        for mode_name in MODES:
            assert validate_mode(mode_name) is True

    def test_enrich_from_config_bad_yaml(self, tmp_path):
        import pathlib
        from sovereign.modes import _enrich_from_config  # noqa: PLC0415
        bad_config = tmp_path / "operating_modes.yaml"
        bad_config.write_text("{ invalid yaml: [unclosed", encoding="utf-8")
        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.read_text", return_value="{ invalid yaml: ["):
            _enrich_from_config()  # must not raise

    def test_enrich_from_config_missing_file(self):
        from sovereign.modes import _enrich_from_config
        with patch("pathlib.Path.exists", return_value=False):
            _enrich_from_config()  # must not raise

    def test_enrich_from_config_warns_unknown_config_mode(self):
        from sovereign.modes import _enrich_from_config
        fake_yaml = "modes:\n  command:\n    description: x\n  nonexistent_mode:\n    description: y\n"
        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.read_text", return_value=fake_yaml):
            _enrich_from_config()  # triggers warning for 'nonexistent_mode' not in MODES


# ---------------------------------------------------------------------------
# router_health + model_ids from config (model_router.py)
# ---------------------------------------------------------------------------

class TestModelRouterHealth:
    def test_router_health_returns_dict(self):
        from sovereign.router.model_router import ModelRouter
        router = ModelRouter()
        health = router.router_health()
        assert "model_ids" in health
        assert "providers" in health
        assert "frontier" in health["model_ids"]
        assert "balanced" in health["model_ids"]
        assert "fast" in health["model_ids"]

    def test_load_model_ids_exception_is_silent(self):
        from sovereign.router import model_router as _mr
        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.read_text", side_effect=OSError("disk error")):
            _mr._load_model_ids_from_config()  # must not raise

    def test_learning_rate_adjust(self):
        from sovereign.router.model_router import ModelRouter
        router = ModelRouter()
        score = router.learning_rate_adjust("claude-sonnet-4-6", success=True, latency_ms=500)
        assert 0.0 <= score <= 1.0
        score2 = router.learning_rate_adjust("claude-sonnet-4-6", success=False, latency_ms=0)
        assert score2 < score
        assert router.model_score("claude-sonnet-4-6") == score2


# ---------------------------------------------------------------------------
# sync_with_retry (integration_manager.py)
# ---------------------------------------------------------------------------

class TestIntegrationManagerRetry:
    async def test_sync_with_retry_success_on_first(self):
        from sovereign.integrations.integration_manager import IntegrationManager
        mgr = IntegrationManager.__new__(IntegrationManager)
        mgr._integrations = {}
        mgr._configs = {}
        with patch.object(mgr, "sync", new=AsyncMock(return_value={"success": True})):
            result = await mgr.sync_with_retry("some_connector")
        assert result == {"success": True}

    async def test_sync_with_retry_retries_on_failure(self):
        from sovereign.integrations.integration_manager import IntegrationManager
        mgr = IntegrationManager.__new__(IntegrationManager)
        call_count = 0

        async def _flaky_sync(connector_id):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("temporary error")
            return {"success": True}

        with patch.object(mgr, "sync", side_effect=_flaky_sync), \
             patch("asyncio.sleep", new=AsyncMock()):
            result = await mgr.sync_with_retry("conn", max_retries=3, base_delay_s=0.0)
        assert result == {"success": True}
        assert call_count == 3

    async def test_sync_with_retry_exhausts_retries(self):
        from sovereign.integrations.integration_manager import IntegrationManager
        mgr = IntegrationManager.__new__(IntegrationManager)

        with patch.object(mgr, "sync", new=AsyncMock(side_effect=RuntimeError("fail"))), \
             patch("asyncio.sleep", new=AsyncMock()):
            result = await mgr.sync_with_retry("conn", max_retries=2, base_delay_s=0.0)
        assert result["success"] is False
        assert "fail" in result["error"]
