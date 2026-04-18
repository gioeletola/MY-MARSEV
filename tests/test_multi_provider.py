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


# ---------------------------------------------------------------------------
# TestOpenAIProvider
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# TestH24WorkerPool
# ---------------------------------------------------------------------------

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
        stats = pool.get_stats()
        assert stats["started"] == 0
        assert stats["crashed"] == 0
        assert stats["restarted"] == 0


# ---------------------------------------------------------------------------
# TestProcessWatchdog
# ---------------------------------------------------------------------------

class TestProcessWatchdog:
    def test_register_single(self):
        from sovereign.infra.watchdog import ProcessWatchdog

        wd = ProcessWatchdog()
        wd.register("my_service", lambda: asyncio.sleep(0))
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

        assert "crasher" in alerts


# ---------------------------------------------------------------------------
# TestHealthAlerter
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# TestSlackIntegration
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# TestNotionIntegration
# ---------------------------------------------------------------------------

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
