<<<<<<< HEAD
"""Tests for multi-provider routing, H24 infrastructure, and live integrations."""
from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

=======
"""
Tests for multi-provider routing, H24 infra, and live integrations.
All HTTP calls are mocked — no network access required.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# TestModelRouter
# ---------------------------------------------------------------------------

class TestModelRouter:
    def setup_method(self):
        from sovereign.router.model_router import ModelRouter
        self.router = ModelRouter()

    def test_low_budget_routes_to_openai_mini(self):
        provider, model = self.router.route_to_provider(
            task_complexity=0.5, budget_limit_usd=0.0005
        )
        assert provider == "openai"
        assert model == "gpt-4o-mini"

    def test_high_complexity_routes_to_anthropic_opus(self):
        provider, model = self.router.route_to_provider(
            task_complexity=0.9, budget_limit_usd=1.0
        )
        assert provider == "anthropic"
        assert model == "claude-opus-4-6"

    def test_default_routes_to_anthropic_sonnet(self):
        provider, model = self.router.route_to_provider(
            task_complexity=0.5, budget_limit_usd=1.0
        )
        assert provider == "anthropic"
        assert model == "claude-sonnet-4-6"

    def test_preferred_openai_respected_on_medium_task(self):
        provider, model = self.router.route_to_provider(
            task_complexity=0.4, budget_limit_usd=1.0, preferred_provider="openai"
        )
        assert provider == "openai"
        assert model == "gpt-4o-mini"

    def test_preferred_gemini_respected_on_medium_task(self):
        provider, model = self.router.route_to_provider(
            task_complexity=0.4, budget_limit_usd=1.0, preferred_provider="gemini"
        )
        assert provider == "gemini"
        assert model == "gemini-1.5-flash"

    def test_budget_rule_overrides_preferred_provider(self):
        provider, model = self.router.route_to_provider(
            task_complexity=0.4,
            budget_limit_usd=0.0005,
            preferred_provider="anthropic",
        )
        assert provider == "openai"
        assert model == "gpt-4o-mini"

    def test_complexity_rule_overrides_preferred_provider(self):
        provider, model = self.router.route_to_provider(
            task_complexity=0.95,
            budget_limit_usd=5.0,
            preferred_provider="openai",
        )
        assert provider == "anthropic"
        assert model == "claude-opus-4-6"

    def test_estimate_cost_anthropic_sonnet(self):
        from sovereign.router.model_router import ModelRouter
        cost = ModelRouter.estimate_cost("anthropic", "claude-sonnet-4-6", 1_000_000, 0)
        assert abs(cost - 3.0) < 0.01

    def test_estimate_cost_openai_gpt4o(self):
        from sovereign.router.model_router import ModelRouter
        cost = ModelRouter.estimate_cost("openai", "gpt-4o", 0, 1_000_000)
        assert abs(cost - 15.0) < 0.01

    def test_estimate_cost_openai_mini(self):
        from sovereign.router.model_router import ModelRouter
        cost = ModelRouter.estimate_cost("openai", "gpt-4o-mini", 1_000_000, 1_000_000)
        assert abs(cost - 0.75) < 0.01

    def test_estimate_cost_unknown_model_zero(self):
        from sovereign.router.model_router import ModelRouter
        cost = ModelRouter.estimate_cost("openai", "does-not-exist", 1_000_000, 1_000_000)
        assert cost == 0.0

    def test_estimate_cost_unknown_provider_zero(self):
        from sovereign.router.model_router import ModelRouter
        cost = ModelRouter.estimate_cost("unknown_provider", "some-model", 100, 100)
        assert cost == 0.0

    def test_estimate_cost_gemini_flash_free(self):
        from sovereign.router.model_router import ModelRouter
        cost = ModelRouter.estimate_cost("gemini", "gemini-1.5-flash", 1_000_000, 1_000_000)
        assert cost == 0.0

>>>>>>> b0c71f2 (feat(multi-provider+h24): OpenAI/Gemini providers, H24 worker pool, watchdog, health alerter, live integrations)

# ---------------------------------------------------------------------------
# TestOpenAIProvider
# ---------------------------------------------------------------------------

<<<<<<< HEAD

class TestOpenAIProvider:
    """Tests for sovereign.models.openai_provider.OpenAIProvider."""

    def _make_provider(self, api_key: str = "") -> object:
        from sovereign.models.openai_provider import OpenAIProvider

        return OpenAIProvider(api_key=api_key)

    def test_available_false_when_no_key(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENAI_API_KEY", None)
            provider = self._make_provider("")
            assert provider.available is False

    def test_available_true_when_key_supplied(self):
        provider = self._make_provider("sk-test")
        assert provider.available is True

    def test_available_true_when_env_key(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env"}):
            provider = self._make_provider()
            assert provider.available is True

    def test_estimate_cost_gpt4o_mini(self):
        from sovereign.models.openai_provider import OpenAIProvider

        p = OpenAIProvider(api_key="x")
        cost = p.estimate_cost("gpt-4o-mini", 1_000_000, 1_000_000)
        assert abs(cost - 0.75) < 1e-6

    def test_estimate_cost_gpt4o(self):
        from sovereign.models.openai_provider import OpenAIProvider

        p = OpenAIProvider(api_key="x")
        cost = p.estimate_cost("gpt-4o", 1_000_000, 1_000_000)
        assert abs(cost - 20.0) < 1e-6

    def test_estimate_cost_unknown_model_falls_back(self):
        from sovereign.models.openai_provider import OpenAIProvider

        p = OpenAIProvider(api_key="x")
        # Unknown model falls back to DEFAULT_MODEL pricing
        cost = p.estimate_cost("does-not-exist", 0, 0)
        assert cost == 0.0

    def test_no_api_key_returns_graceful_dict(self):
        """complete() with no key returns {content: '', error: 'no_api_key'}."""
        from sovereign.models.openai_provider import OpenAIProvider

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENAI_API_KEY", None)
            p = OpenAIProvider(api_key="")
            result = asyncio.get_event_loop().run_until_complete(
                p.complete(messages=[{"role": "user", "content": "hi"}])
            )
        assert isinstance(result, dict)
        assert result["content"] == ""
        assert result["error"] == "no_api_key"

    def test_normalized_response_shape(self):
        """Mock httpx to verify the returned dict has the expected keys."""
        from sovereign.models.openai_provider import OpenAIProvider
=======
class TestOpenAIProvider:
    def test_no_api_key_returns_stub(self):
        from sovereign.models.openai_provider import OpenAIProvider
        from sovereign.models.base_provider import ProviderStatus
        provider = OpenAIProvider(api_key="")
        assert provider._status == ProviderStatus.UNAVAILABLE

    @pytest.mark.asyncio
    async def test_complete_no_key_returns_stub_response(self):
        from sovereign.models.openai_provider import OpenAIProvider
        from sovereign.models.base_provider import CompletionRequest
        provider = OpenAIProvider(api_key="")
        req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
        resp = await provider.complete(req)
        assert "unavailable" in resp.content.lower() or "no api" in resp.content.lower()

    @pytest.mark.asyncio
    async def test_complete_normalizes_response(self):
        from sovereign.models.openai_provider import OpenAIProvider
        from sovereign.models.base_provider import CompletionRequest
>>>>>>> b0c71f2 (feat(multi-provider+h24): OpenAI/Gemini providers, H24 worker pool, watchdog, health alerter, live integrations)

        fake_response = {
            "id": "chatcmpl-test",
            "model": "gpt-4o-mini",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Hello!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

<<<<<<< HEAD
        async def fake_post(*_args, **_kwargs):
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = fake_response
            return mock_resp

        p = OpenAIProvider(api_key="sk-fake")
        with patch("httpx.AsyncClient.post", new=fake_post):
            result = asyncio.get_event_loop().run_until_complete(
                p.complete(
                    messages=[{"role": "user", "content": "hi"}],
                    model="gpt-4o-mini",
                )
            )

        assert result["content"] == "Hello!"
        assert result["provider"] == "openai"
        assert "usage" in result
        assert result["usage"]["input_tokens"] == 10
        assert result["usage"]["output_tokens"] == 5
        assert "cost_usd" in result
        assert result["error"] is None

    def test_models_dict_has_three_entries(self):
        from sovereign.models.openai_provider import OpenAIProvider

        assert len(OpenAIProvider.MODELS) == 3

    def test_default_model_is_gpt4o_mini(self):
        from sovereign.models.openai_provider import OpenAIProvider

        assert OpenAIProvider.DEFAULT_MODEL == "gpt-4o-mini"


# ---------------------------------------------------------------------------
# TestGeminiProvider
# ---------------------------------------------------------------------------


class TestGeminiProvider:
    """Tests for sovereign.models.gemini_provider.GeminiProvider."""

    def _make_provider(self, api_key: str = "") -> object:
        from sovereign.models.gemini_provider import GeminiProvider

        return GeminiProvider(api_key=api_key)

    def test_available_false_when_no_key(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GEMINI_API_KEY", None)
            provider = self._make_provider("")
            assert provider.available is False

    def test_available_true_when_key_supplied(self):
        provider = self._make_provider("ai-test")
        assert provider.available is True

    def test_estimate_cost_flash(self):
        from sovereign.models.gemini_provider import GeminiProvider

        p = GeminiProvider(api_key="x")
        cost = p.estimate_cost("gemini-1.5-flash", 1_000_000, 1_000_000)
        assert abs(cost - 0.375) < 1e-6

    def test_estimate_cost_pro(self):
        from sovereign.models.gemini_provider import GeminiProvider

        p = GeminiProvider(api_key="x")
        cost = p.estimate_cost("gemini-1.5-pro", 1_000_000, 1_000_000)
        assert abs(cost - 14.0) < 1e-6

    def test_no_api_key_returns_graceful_dict(self):
        from sovereign.models.gemini_provider import GeminiProvider

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GEMINI_API_KEY", None)
            p = GeminiProvider(api_key="")
            result = asyncio.get_event_loop().run_until_complete(
                p.complete(messages=[{"role": "user", "content": "hi"}])
            )
        assert result["content"] == ""
        assert result["error"] == "no_api_key"

    def test_normalized_response_shape(self):
        from sovereign.models.gemini_provider import GeminiProvider

        fake_response = {
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [{"text": "Gemini says hi"}],
                    },
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 8,
                "candidatesTokenCount": 4,
            },
        }

        async def fake_post(*_args, **_kwargs):
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = fake_response
            return mock_resp

        p = GeminiProvider(api_key="ai-fake")
        with patch("httpx.AsyncClient.post", new=fake_post):
            result = asyncio.get_event_loop().run_until_complete(
                p.complete(
                    messages=[{"role": "user", "content": "hi"}],
                    model="gemini-1.5-flash",
                )
            )

        assert result["content"] == "Gemini says hi"
        assert result["provider"] == "gemini"
        assert result["usage"]["input_tokens"] == 8
        assert result["usage"]["output_tokens"] == 4
        assert result["error"] is None

    def test_default_model_is_flash(self):
        from sovereign.models.gemini_provider import GeminiProvider

        assert GeminiProvider.DEFAULT_MODEL == "gemini-1.5-flash"

    def test_models_dict_has_two_entries(self):
        from sovereign.models.gemini_provider import GeminiProvider

        assert len(GeminiProvider.MODELS) == 2


# ---------------------------------------------------------------------------
# TestModelRouter
# ---------------------------------------------------------------------------


class TestModelRouter:
    """Tests for the new methods on sovereign.router.model_router.ModelRouter."""

    def _router(self):
        from sovereign.router.model_router import ModelRouter

        return ModelRouter()

    def test_route_cheap_and_simple_goes_to_openai(self):
        router = self._router()
        provider, model = router.route_to_provider(
            task_complexity=0.3, budget_limit_usd=0.0005
        )
        assert provider == "openai"
        assert model == "gpt-4o-mini"

    def test_route_complex_goes_to_anthropic_opus(self):
        router = self._router()
        provider, model = router.route_to_provider(
            task_complexity=0.9, budget_limit_usd=1.0
        )
        assert provider == "anthropic"
        assert model == "claude-opus-4-7"

    def test_route_default_goes_to_anthropic_sonnet(self):
        router = self._router()
        provider, model = router.route_to_provider(
            task_complexity=0.5, budget_limit_usd=0.5
        )
        assert provider == "anthropic"
        assert model == "claude-sonnet-4-6"

    def test_preferred_provider_openai(self):
        router = self._router()
        provider, model = router.route_to_provider(
            task_complexity=0.5,
            budget_limit_usd=0.5,
            preferred_provider="openai",
        )
        assert provider == "openai"

    def test_preferred_provider_gemini(self):
        router = self._router()
        provider, model = router.route_to_provider(
            task_complexity=0.5,
            budget_limit_usd=0.5,
            preferred_provider="gemini",
        )
        assert provider == "gemini"

    def test_preferred_unknown_falls_back(self):
        router = self._router()
        provider, model = router.route_to_provider(
            task_complexity=0.5,
            budget_limit_usd=0.5,
            preferred_provider="mystery_provider",
        )
        # Falls back to default anthropic routing
        assert provider == "anthropic"

    def test_estimate_cost_anthropic_sonnet(self):
        router = self._router()
        cost = router.estimate_cost("anthropic", "claude-sonnet-4-6", 1_000_000, 1_000_000)
        assert abs(cost - 18.0) < 1e-6

    def test_estimate_cost_openai_mini(self):
        router = self._router()
        cost = router.estimate_cost("openai", "gpt-4o-mini", 1_000_000, 1_000_000)
        assert abs(cost - 0.75) < 1e-6

    def test_estimate_cost_unknown_returns_zero(self):
        router = self._router()
        cost = router.estimate_cost("alien", "unknown-model", 100, 100)
        assert cost == 0.0

    def test_route_returns_tuple(self):
        router = self._router()
        result = router.route_to_provider(0.5, 0.5)
        assert isinstance(result, tuple)
        assert len(result) == 2
=======
        mock_resp = MagicMock()
        mock_resp.json.return_value = fake_response
        mock_resp.raise_for_status = MagicMock()

        provider = OpenAIProvider(api_key="sk-test")
        req = CompletionRequest(
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-4o-mini",
        )

        with patch("httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.post = AsyncMock(return_value=mock_resp)
            resp = await provider.complete(req)

        assert resp.content == "Hello!"
        assert resp.model == "gpt-4o-mini"
        assert resp.input_tokens == 10
        assert resp.output_tokens == 5
        assert resp.provider == "openai"

    @pytest.mark.asyncio
    async def test_stream_flag_calls_sse_endpoint(self):
        from sovereign.models.openai_provider import OpenAIProvider
        from sovereign.models.base_provider import CompletionRequest

        async def mock_aiter_lines():
            for line in [
                'data: {"choices":[{"delta":{"content":"Hello"}}]}',
                'data: {"choices":[{"delta":{"content":" world"}}]}',
                "data: [DONE]",
            ]:
                yield line

        mock_stream_resp = MagicMock()
        mock_stream_resp.raise_for_status = MagicMock()
        mock_stream_resp.aiter_lines = mock_aiter_lines
        mock_stream_resp.__aenter__ = AsyncMock(return_value=mock_stream_resp)
        mock_stream_resp.__aexit__ = AsyncMock(return_value=False)

        provider = OpenAIProvider(api_key="sk-test")
        req = CompletionRequest(
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-4o-mini",
            stream=True,
        )

        chunks: list[str] = []
        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = MockClient.return_value.__aenter__.return_value
            mock_client_instance.stream = MagicMock(return_value=mock_stream_resp)
            async for token in provider.stream(req):
                chunks.append(token)

        assert "".join(chunks) == "Hello world"

    def test_estimate_cost_gpt4o_mini(self):
        from sovereign.models.openai_provider import OpenAIProvider
        cost = OpenAIProvider.estimate_cost("gpt-4o-mini", 1_000_000, 1_000_000)
        assert abs(cost - 0.75) < 0.01

    @pytest.mark.asyncio
    async def test_health_check_no_key_unavailable(self):
        from sovereign.models.openai_provider import OpenAIProvider
        from sovereign.models.base_provider import ProviderStatus
        provider = OpenAIProvider(api_key="")
        status = await provider.health_check()
        assert status == ProviderStatus.UNAVAILABLE
>>>>>>> b0c71f2 (feat(multi-provider+h24): OpenAI/Gemini providers, H24 worker pool, watchdog, health alerter, live integrations)


# ---------------------------------------------------------------------------
# TestH24WorkerPool
# ---------------------------------------------------------------------------

<<<<<<< HEAD

class TestH24WorkerPool:
    def _make_pool(self, n: int = 2):
        from sovereign.infra.worker_manager import H24WorkerPool

        return H24WorkerPool(n_workers=n)

    def test_init_stats_structure(self):
        pool = self._make_pool()
        stats = pool.get_stats()
        assert "started" in stats
        assert "crashed" in stats
        assert "restarted" in stats

    def test_init_stats_all_zero(self):
        pool = self._make_pool()
=======
class TestH24WorkerPool:
    @pytest.mark.asyncio
    async def test_start_stop_basic(self):
        from sovereign.infra.worker_manager import H24WorkerPool

        pool = H24WorkerPool(n_workers=2)
        stop = asyncio.Event()
        task = asyncio.create_task(pool.start(stop))
        await asyncio.sleep(0.05)
        stop.set()
        await asyncio.wait_for(task, timeout=5.0)

        stats = pool.get_stats()
        assert stats["started"] >= 2

    @pytest.mark.asyncio
    async def test_processes_tasks_from_queue(self):
        from sovereign.infra.worker_manager import H24WorkerPool

        q: asyncio.Queue = asyncio.Queue()
        results: list[int] = []

        pool = H24WorkerPool(n_workers=1, task_queue=q)
        stop = asyncio.Event()
        task = asyncio.create_task(pool.start(stop))

        await asyncio.sleep(0.02)
        q.put_nowait(lambda: results.append(42))
        await asyncio.sleep(0.1)
        stop.set()
        await asyncio.wait_for(task, timeout=5.0)

        assert 42 in results

    @pytest.mark.asyncio
    async def test_crash_increments_restarted(self):
        from sovereign.infra.worker_manager import H24WorkerPool

        crash_count = 0

        async def crashing_task():
            nonlocal crash_count
            crash_count += 1
            if crash_count <= 1:
                raise RuntimeError("boom")

        q: asyncio.Queue = asyncio.Queue()
        q.put_nowait(crashing_task)

        # Use short monitor interval so the crash is detected quickly
        pool = H24WorkerPool(n_workers=1, task_queue=q, monitor_interval_s=0.05)
        stop = asyncio.Event()
        task = asyncio.create_task(pool.start(stop))
        # Give time for: worker starts → processes task → crashes → monitor detects → restarts
        await asyncio.sleep(0.5)
        stop.set()
        await asyncio.wait_for(task, timeout=5.0)

        stats = pool.get_stats()
        assert stats["restarted"] >= 1

    def test_get_stats_initial(self):
        from sovereign.infra.worker_manager import H24WorkerPool

        pool = H24WorkerPool(n_workers=3)
>>>>>>> b0c71f2 (feat(multi-provider+h24): OpenAI/Gemini providers, H24 worker pool, watchdog, health alerter, live integrations)
        stats = pool.get_stats()
        assert stats["started"] == 0
        assert stats["crashed"] == 0
        assert stats["restarted"] == 0

<<<<<<< HEAD
    def test_n_workers_stored(self):
        from sovereign.infra.worker_manager import H24WorkerPool

        pool = H24WorkerPool(n_workers=5)
        assert pool._n == 5

    def test_start_increments_started(self):
        from sovereign.infra.worker_manager import H24WorkerPool

        pool = H24WorkerPool(n_workers=2)

        async def run():
            stop = asyncio.Event()
            stop.set()
            await pool.start(stop)

        asyncio.get_event_loop().run_until_complete(run())
        assert pool.get_stats()["started"] == 2

    def test_crash_in_worker_increments_crashed(self):
        from sovereign.infra.worker_manager import H24WorkerPool

        pool = H24WorkerPool(n_workers=1, task_queue=asyncio.Queue())
        items_processed = []

        async def run():
            stop = asyncio.Event()
            # Put one item, then immediately set stop
            await pool._queue.put("item")

            async def fake_process(worker_id, item):
                items_processed.append(item)
                stop.set()
                raise RuntimeError("intentional crash")

            pool._process = fake_process  # type: ignore[method-assign]
            await asyncio.wait_for(pool.start(stop), timeout=3.0)

        asyncio.get_event_loop().run_until_complete(run())
        assert pool.get_stats()["crashed"] >= 1

=======
>>>>>>> b0c71f2 (feat(multi-provider+h24): OpenAI/Gemini providers, H24 worker pool, watchdog, health alerter, live integrations)

# ---------------------------------------------------------------------------
# TestProcessWatchdog
# ---------------------------------------------------------------------------

<<<<<<< HEAD

class TestProcessWatchdog:
    def test_register_adds_to_registry(self):
=======
class TestProcessWatchdog:
    def test_register_single(self):
>>>>>>> b0c71f2 (feat(multi-provider+h24): OpenAI/Gemini providers, H24 worker pool, watchdog, health alerter, live integrations)
        from sovereign.infra.watchdog import ProcessWatchdog

        wd = ProcessWatchdog()
        wd.register("my_service", lambda: asyncio.sleep(0))
<<<<<<< HEAD
        assert "my_service" in wd._registry

    def test_get_status_structure(self):
        from sovereign.infra.watchdog import ProcessWatchdog

        wd = ProcessWatchdog()
        wd.register("svc1", lambda: asyncio.sleep(0))
        status = wd.get_status()
        assert "svc1" in status
        assert "restart_count" in status["svc1"]
        assert "last_fail" in status["svc1"]
        assert "status" in status["svc1"]

    def test_initial_restart_count_is_zero(self):
        from sovereign.infra.watchdog import ProcessWatchdog

        wd = ProcessWatchdog()
        wd.register("svc2", lambda: asyncio.sleep(0))
        assert wd.get_status()["svc2"]["restart_count"] == 0

    def test_coroutine_runs_and_stops(self):
        from sovereign.infra.watchdog import ProcessWatchdog

        wd = ProcessWatchdog()
        stop = asyncio.Event()
        ran = []

        async def my_coro():
            ran.append(True)
            stop.set()

        wd.register("coro", my_coro)

        async def run():
            await asyncio.wait_for(wd.start_all(stop), timeout=2.0)

        asyncio.get_event_loop().run_until_complete(run())
        assert ran

    def test_alert_callback_called_on_crash(self):
        from sovereign.infra.watchdog import ProcessWatchdog

        alerts = []

        wd = ProcessWatchdog(alert_callback=lambda name, exc: alerts.append(name))
        stop = asyncio.Event()
        crash_count = [0]

        async def crashing():
            crash_count[0] += 1
            if crash_count[0] >= 2:
                stop.set()
            raise RuntimeError("boom")

        wd.register("crasher", crashing)

        async def run():
            await asyncio.wait_for(wd.start_all(stop), timeout=5.0)

        asyncio.get_event_loop().run_until_complete(run())
        assert len(alerts) >= 1
=======
        status = wd.get_status()
        assert "my_service" in status
        assert status["my_service"]["restart_count"] == 0

    def test_register_multiple(self):
        from sovereign.infra.watchdog import ProcessWatchdog

        wd = ProcessWatchdog()
        for name in ("svc_a", "svc_b", "svc_c"):
            wd.register(name, lambda: asyncio.sleep(0))
        assert len(wd.get_status()) == 3

    def test_get_status_before_start_not_started(self):
        from sovereign.infra.watchdog import ProcessWatchdog

        wd = ProcessWatchdog()
        wd.register("svc", lambda: asyncio.sleep(0))
        status = wd.get_status()
        assert status["svc"]["task_state"] == "not_started"

    @pytest.mark.asyncio
    async def test_supervise_restart_on_crash(self):
        from sovereign.infra.watchdog import ProcessWatchdog

        call_count = 0

        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("first call fails")
            await asyncio.sleep(10)

        wd = ProcessWatchdog()
        wd.register("flaky", flaky)
        stop = asyncio.Event()
        supervise_task = asyncio.create_task(wd.start_all(stop))
        await asyncio.sleep(0.2)
        stop.set()
        await asyncio.wait_for(supervise_task, timeout=5.0)

        status = wd.get_status()
        assert status["flaky"]["restart_count"] >= 1

    @pytest.mark.asyncio
    async def test_alert_callback_called_on_crash(self):
        from sovereign.infra.watchdog import ProcessWatchdog

        alerts: list[str] = []

        def on_alert(name: str, exc: Exception) -> None:
            alerts.append(name)

        async def crasher():
            raise ValueError("oh no")

        wd = ProcessWatchdog(alert_callback=on_alert)
        wd.register("crasher", crasher)
        stop = asyncio.Event()
        t = asyncio.create_task(wd.start_all(stop))
        await asyncio.sleep(0.15)
        stop.set()
        await asyncio.wait_for(t, timeout=5.0)

>>>>>>> b0c71f2 (feat(multi-provider+h24): OpenAI/Gemini providers, H24 worker pool, watchdog, health alerter, live integrations)
        assert "crasher" in alerts


# ---------------------------------------------------------------------------
# TestHealthAlerter
# ---------------------------------------------------------------------------

<<<<<<< HEAD

class TestHealthAlerter:
    def _make_alerter(self, threshold: int = 3) -> object:
        from sovereign.infra.health_alerter import HealthAlerter

        return HealthAlerter(threshold=threshold)

    def test_initial_stats(self):
        alerter = self._make_alerter()
        stats = alerter.get_stats()
        assert stats["alerts_sent"] == 0
        assert stats["consecutive_failures"] == 0
        assert stats["last_alert_ts"] is None

    def test_healthy_resets_counter(self):
        alerter = self._make_alerter()
        alerter._consecutive_failures = 5

        async def run():
            await alerter.check_and_alert({"overall": "healthy"})

        asyncio.get_event_loop().run_until_complete(run())
        assert alerter._consecutive_failures == 0

    def test_unhealthy_increments_counter(self):
        alerter = self._make_alerter(threshold=10)

        async def run():
            await alerter.check_and_alert({"overall": "degraded"})

        asyncio.get_event_loop().run_until_complete(run())
        assert alerter._consecutive_failures == 1

    def test_alert_fires_at_threshold(self):
        alerter = self._make_alerter(threshold=3)
        alerter._consecutive_failures = 2  # one more will trigger

        async def run():
            await alerter.check_and_alert({"overall": "down"})

        asyncio.get_event_loop().run_until_complete(run())
        assert alerter.get_stats()["alerts_sent"] == 1

    def test_no_alert_below_threshold(self):
        alerter = self._make_alerter(threshold=5)

        async def run():
            for _ in range(4):
                await alerter.check_and_alert({"overall": "degraded"})

        asyncio.get_event_loop().run_until_complete(run())
        assert alerter.get_stats()["alerts_sent"] == 0

    def test_telegram_send_graceful_on_error(self):
        from sovereign.infra.health_alerter import HealthAlerter

        alerter = HealthAlerter(telegram_token="bad-token", chat_id="123", threshold=1)

        async def run():
            return await alerter._send_telegram("test message")

        # Should not raise; returns False on error
        result = asyncio.get_event_loop().run_until_complete(run())
        assert isinstance(result, bool)
=======
class TestHealthAlerter:
    @pytest.mark.asyncio
    async def test_no_alert_below_threshold(self):
        from sovereign.infra.health_alerter import HealthAlerter

        ha = HealthAlerter(threshold_failures=3)
        for _ in range(2):
            await ha.check_and_alert({"overall": "degraded"})
        assert ha.get_stats()["total_alerts_sent"] == 0

    @pytest.mark.asyncio
    async def test_alert_at_threshold(self):
        from sovereign.infra.health_alerter import HealthAlerter

        ha = HealthAlerter(threshold_failures=3)
        ha._send_telegram = AsyncMock(return_value=True)  # type: ignore[method-assign]
        for _ in range(3):
            await ha.check_and_alert({"overall": "unhealthy"})
        assert ha.get_stats()["total_alerts_sent"] >= 1

    @pytest.mark.asyncio
    async def test_no_alert_when_healthy(self):
        from sovereign.infra.health_alerter import HealthAlerter

        ha = HealthAlerter(threshold_failures=1)
        await ha.check_and_alert({"overall": "healthy"})
        assert ha.get_stats()["total_alerts_sent"] == 0

    @pytest.mark.asyncio
    async def test_consecutive_reset_on_recovery(self):
        from sovereign.infra.health_alerter import HealthAlerter

        ha = HealthAlerter(threshold_failures=5)
        for _ in range(2):
            await ha.check_and_alert({"overall": "degraded"})
        await ha.check_and_alert({"overall": "healthy"})
        assert ha._consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_telegram_not_configured_returns_false(self):
        from sovereign.infra.health_alerter import HealthAlerter

        ha = HealthAlerter(telegram_token="", chat_id="")
        result = await ha._send_telegram("test message")
        assert result is False

    def test_get_stats_keys(self):
        from sovereign.infra.health_alerter import HealthAlerter

        ha = HealthAlerter(threshold_failures=3)
        stats = ha.get_stats()
        assert "total_checks" in stats
        assert "consecutive_failures" in stats
        assert "total_alerts_sent" in stats
        assert "threshold" in stats


# ---------------------------------------------------------------------------
# TestWebhookIntegration
# ---------------------------------------------------------------------------

class TestWebhookIntegration:
    def test_push_no_url_returns_error(self):
        from sovereign.integrations.webhook_integration import WebhookIntegration

        wi = WebhookIntegration(webhook_url="")
        result = wi.push("event", {"foo": "bar"})
        assert result["ok"] is False

    def test_push_returns_dict_with_ok_field(self):
        from sovereign.integrations.webhook_integration import WebhookIntegration

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.is_success = True

        wi = WebhookIntegration(webhook_url="https://example.com/hook")
        with patch("httpx.Client") as MockClient:
            MockClient.return_value.__enter__.return_value.post.return_value = mock_resp
            result = wi.push("event", {"foo": "bar"})

        assert "ok" in result
        assert result["ok"] is True
        assert result["status_code"] == 200

    def test_connect_sets_url_from_config(self):
        from sovereign.integrations.webhook_integration import WebhookIntegration
        from sovereign.integrations.base_integration import IntegrationConfig, IntegrationStatus

        wi = WebhookIntegration()
        config = IntegrationConfig(
            integration_id="webhook",
            name="wh",
            enabled=True,
            settings={"webhook_url": "https://my-hook.example.com"},
        )
        ok = wi.connect(config)
        assert ok is True
        assert wi._webhook_url == "https://my-hook.example.com"
        assert wi.status == IntegrationStatus.CONNECTED

    def test_fetch_returns_empty(self):
        from sovereign.integrations.webhook_integration import WebhookIntegration

        wi = WebhookIntegration(webhook_url="https://example.com/hook")
        result = wi.fetch("anything", {})
        assert result == {}
>>>>>>> b0c71f2 (feat(multi-provider+h24): OpenAI/Gemini providers, H24 worker pool, watchdog, health alerter, live integrations)


# ---------------------------------------------------------------------------
# TestSlackIntegration
# ---------------------------------------------------------------------------

<<<<<<< HEAD

class TestSlackIntegration:
    def _make_integration(self):
        from sovereign.integrations.slack_integration import SlackIntegration

        return SlackIntegration()

    def _make_config(self, webhook_url: str = "", bot_token: str = ""):
        from sovereign.integrations.base_integration import IntegrationConfig

        return IntegrationConfig(
            integration_id="slack",
            name="Slack",
            enabled=True,
            credentials={
                "webhook_url": webhook_url,
                "bot_token": bot_token,
                "default_channel": "#test",
            },
        )

    def test_connect_returns_false_when_no_creds(self):
        integration = self._make_integration()
        config = self._make_config()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SLACK_WEBHOOK_URL", None)
            os.environ.pop("SLACK_BOT_TOKEN", None)
            result = integration.connect(config)
        assert result is False

    def test_connect_returns_true_with_webhook(self):
        integration = self._make_integration()
        config = self._make_config(webhook_url="https://hooks.slack.com/test")
        result = integration.connect(config)
        assert result is True

    def test_disconnect_returns_true(self):
        integration = self._make_integration()
        assert integration.disconnect() is True

    def test_push_returns_dict(self):
        integration = self._make_integration()
        integration._webhook_url = "https://hooks.slack.com/test"

        integration._http = MagicMock()
        integration._http.post = AsyncMock(return_value=MagicMock(status_code=200, text="ok"))

        result = integration.push("message", {"text": "hello"})
        assert isinstance(result, dict)

    def test_test_connection_false_without_creds(self):
        integration = self._make_integration()
        assert integration.test_connection() is False

    def test_test_connection_true_with_webhook(self):
        integration = self._make_integration()
        integration._webhook_url = "https://hooks.slack.com/test"
        assert integration.test_connection() is True
=======
class TestSlackIntegration:
    def test_push_no_credentials_returns_error(self):
        from sovereign.integrations.slack_integration import SlackIntegration

        si = SlackIntegration(webhook_url="", bot_token="")
        result = si.push("message", {"text": "hello"})
        assert "ok" in result
        assert result["ok"] is False

    def test_push_via_webhook_returns_dict(self):
        from sovereign.integrations.slack_integration import SlackIntegration

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.is_success = True
        mock_resp.text = "ok"

        si = SlackIntegration(webhook_url="https://hooks.slack.com/test")
        with patch("httpx.Client") as MockClient:
            MockClient.return_value.__enter__.return_value.post.return_value = mock_resp
            result = si.push("message", {"text": "Hello Slack!"})

        assert "ok" in result
        assert result["ok"] is True

    def test_push_unknown_resource_returns_error(self):
        from sovereign.integrations.slack_integration import SlackIntegration

        si = SlackIntegration(webhook_url="https://hooks.slack.com/test")
        result = si.push("unknown", {})
        assert result["ok"] is False

    def test_connect_sets_webhook_url(self):
        from sovereign.integrations.slack_integration import SlackIntegration
        from sovereign.integrations.base_integration import IntegrationConfig, IntegrationStatus

        si = SlackIntegration()
        config = IntegrationConfig(
            integration_id="slack",
            name="slack",
            enabled=True,
            credentials={"webhook_url": "https://hooks.slack.com/services/X"},
        )
        ok = si.connect(config)
        assert ok is True
        assert si._webhook_url == "https://hooks.slack.com/services/X"
        assert si.status == IntegrationStatus.CONNECTED
>>>>>>> b0c71f2 (feat(multi-provider+h24): OpenAI/Gemini providers, H24 worker pool, watchdog, health alerter, live integrations)


# ---------------------------------------------------------------------------
# TestNotionIntegration
# ---------------------------------------------------------------------------

<<<<<<< HEAD

class TestNotionIntegration:
    def _make_integration(self):
        from sovereign.integrations.notion_integration import NotionIntegration

        return NotionIntegration()

    def _make_config(self, api_key: str = "", database_id: str = "db-123"):
        from sovereign.integrations.base_integration import IntegrationConfig

        return IntegrationConfig(
            integration_id="notion",
            name="Notion",
            enabled=True,
            credentials={"api_key": api_key, "default_database_id": database_id},
        )

    def test_connect_returns_false_when_no_key(self):
        integration = self._make_integration()
        config = self._make_config(api_key="")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NOTION_API_KEY", None)
            result = integration.connect(config)
        assert result is False

    def test_connect_returns_true_with_key(self):
        integration = self._make_integration()
        config = self._make_config(api_key="secret_token")
        result = integration.connect(config)
        assert result is True

    def test_disconnect_returns_true(self):
        integration = self._make_integration()
        assert integration.disconnect() is True

    def test_fetch_returns_dict_no_key(self):
        integration = self._make_integration()
        result = integration.fetch("page", {"page_id": "abc"})
        assert isinstance(result, dict)

    def test_push_returns_dict_no_key(self):
        integration = self._make_integration()
        result = integration.push("page", {"title": "Test", "content": "Hello"})
        assert isinstance(result, dict)

    def test_test_connection_false_without_key(self):
        integration = self._make_integration()
        assert integration.test_connection() is False

    def test_test_connection_true_with_key(self):
        integration = self._make_integration()
        integration._api_key = "secret_token"
        assert integration.test_connection() is True
=======
class TestNotionIntegration:
    def test_fetch_page_no_key_returns_empty(self):
        from sovereign.integrations.notion_integration import NotionIntegration

        ni = NotionIntegration(api_key="")
        result = ni.fetch("page", {"page_id": "abc123"})
        assert result == {}

    def test_push_page_no_key_returns_error(self):
        from sovereign.integrations.notion_integration import NotionIntegration

        ni = NotionIntegration(api_key="")
        result = ni.push("page", {})
        assert result["ok"] is False

    def test_fetch_page_returns_dict(self):
        from sovereign.integrations.notion_integration import NotionIntegration

        fake_page = {"id": "page-123", "object": "page", "properties": {}}
        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.json.return_value = fake_page

        ni = NotionIntegration(api_key="secret_test")
        with patch("httpx.Client") as MockClient:
            MockClient.return_value.__enter__.return_value.get.return_value = mock_resp
            result = ni.fetch("page", {"page_id": "page-123"})

        assert result.get("id") == "page-123"

    def test_push_page_creates_page(self):
        from sovereign.integrations.notion_integration import NotionIntegration

        fake_page = {"id": "new-page-456", "object": "page"}
        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.json.return_value = fake_page

        ni = NotionIntegration(api_key="secret_test")
        with patch("httpx.Client") as MockClient:
            MockClient.return_value.__enter__.return_value.post.return_value = mock_resp
            result = ni.push("page", {"parent": {"database_id": "db-1"}})

        assert result["ok"] is True
        assert result["id"] == "new-page-456"

    def test_fetch_search_returns_results(self):
        from sovereign.integrations.notion_integration import NotionIntegration

        fake_results = {"object": "list", "results": [{"id": "r1"}]}
        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.json.return_value = fake_results

        ni = NotionIntegration(api_key="secret_test")
        with patch("httpx.Client") as MockClient:
            MockClient.return_value.__enter__.return_value.post.return_value = mock_resp
            result = ni.fetch("search", {"query": "meeting notes"})

        assert "results" in result

    def test_connect_sets_api_key(self):
        from sovereign.integrations.notion_integration import NotionIntegration
        from sovereign.integrations.base_integration import IntegrationConfig, IntegrationStatus

        ni = NotionIntegration()
        config = IntegrationConfig(
            integration_id="notion",
            name="notion",
            enabled=True,
            credentials={"api_key": "secret_abc"},
        )
        ok = ni.connect(config)
        assert ok is True
        assert ni._api_key == "secret_abc"
        assert ni.status == IntegrationStatus.CONNECTED
>>>>>>> b0c71f2 (feat(multi-provider+h24): OpenAI/Gemini providers, H24 worker pool, watchdog, health alerter, live integrations)
