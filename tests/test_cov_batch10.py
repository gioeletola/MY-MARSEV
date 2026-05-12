"""Coverage batch 10 — new model providers: Perplexity, Kimi, ProviderDispatcher."""
from __future__ import annotations

import asyncio
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# PerplexityProvider
# ---------------------------------------------------------------------------

class TestPerplexityProviderNoKey(unittest.TestCase):
    def setUp(self):
        os.environ.pop("PERPLEXITY_API_KEY", None)
        from sovereign.models.perplexity_provider import PerplexityProvider
        self.provider = PerplexityProvider()

    def test_status_unavailable_without_key(self):
        from sovereign.models.base_provider import ProviderStatus
        self.assertEqual(self.provider._status, ProviderStatus.UNAVAILABLE)

    def test_complete_stub_without_key(self):
        from sovereign.models.base_provider import CompletionRequest
        req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
        resp = asyncio.run(self.provider.complete(req))
        self.assertIn("Perplexity unavailable", resp.content)

    def test_stream_stub_without_key(self):
        from sovereign.models.base_provider import CompletionRequest
        req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
        async def collect():
            tokens = []
            async for t in self.provider.stream(req):
                tokens.append(t)
            return tokens
        tokens = asyncio.run(collect())
        self.assertTrue(any("Perplexity unavailable" in t for t in tokens))

    def test_health_check_unavailable(self):
        from sovereign.models.base_provider import ProviderStatus
        status = asyncio.run(self.provider.health_check())
        self.assertEqual(status, ProviderStatus.UNAVAILABLE)

    def test_estimate_cost(self):
        from sovereign.models.perplexity_provider import PerplexityProvider
        cost = PerplexityProvider.estimate_cost("sonar", 1_000_000, 1_000_000)
        self.assertGreater(cost, 0.0)

    def test_estimate_cost_unknown_model(self):
        from sovereign.models.perplexity_provider import PerplexityProvider
        cost = PerplexityProvider.estimate_cost("unknown-model", 100, 100)
        self.assertEqual(cost, 0.0)

    def test_build_body_with_system(self):
        from sovereign.models.base_provider import CompletionRequest
        req = CompletionRequest(
            messages=[{"role": "user", "content": "hi"}],
            system="Be helpful",
            model="sonar",
        )
        body = self.provider._build_body(req)
        self.assertEqual(body["messages"][0]["role"], "system")
        self.assertEqual(body["messages"][0]["content"], "Be helpful")

    def test_build_body_stream_flag(self):
        from sovereign.models.base_provider import CompletionRequest
        req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
        body = self.provider._build_body(req, stream=True)
        self.assertTrue(body["stream"])


class TestPerplexityProviderWithKey(unittest.TestCase):
    def setUp(self):
        os.environ["PERPLEXITY_API_KEY"] = "pplx-test-key"
        from sovereign.models.perplexity_provider import PerplexityProvider
        self.provider = PerplexityProvider()

    def tearDown(self):
        os.environ.pop("PERPLEXITY_API_KEY", None)

    def test_status_available_with_key(self):
        from sovereign.models.base_provider import ProviderStatus
        self.assertEqual(self.provider._status, ProviderStatus.AVAILABLE)

    def test_headers_contain_bearer(self):
        headers = self.provider._headers()
        self.assertIn("Bearer pplx-test-key", headers["Authorization"])

    def test_complete_success(self):
        from sovereign.models.base_provider import CompletionRequest
        mock_data = {
            "choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}],
            "model": "sonar",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_data
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            MockClient.return_value = mock_client

            req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
            resp = asyncio.run(self.provider.complete(req))

        self.assertEqual(resp.content, "hello")
        self.assertEqual(resp.input_tokens, 10)
        self.assertEqual(resp.output_tokens, 5)

    def test_complete_records_error_on_exception(self):
        from sovereign.models.base_provider import CompletionRequest
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=RuntimeError("net error"))
            MockClient.return_value = mock_client

            req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
            with self.assertRaises(RuntimeError):
                asyncio.run(self.provider.complete(req))

        self.assertEqual(self.provider._error_count, 1)

    def test_stream_success(self):
        from sovereign.models.base_provider import CompletionRequest

        sse_lines = [
            'data: {"choices":[{"delta":{"content":"tok1"},"finish_reason":null}]}',
            'data: {"choices":[{"delta":{"content":"tok2"},"finish_reason":null}]}',
            "data: [DONE]",
        ]

        async def fake_aiter_lines():
            for line in sse_lines:
                yield line

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.aiter_lines = fake_aiter_lines
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_client = MagicMock()
        mock_client.stream = MagicMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
            async def collect():
                tokens = []
                async for t in self.provider.stream(req):
                    tokens.append(t)
                return tokens
            tokens = asyncio.run(collect())

        self.assertIn("tok1", tokens)
        self.assertIn("tok2", tokens)


# ---------------------------------------------------------------------------
# ProviderDispatcher
# ---------------------------------------------------------------------------

class TestProviderDispatcher(unittest.TestCase):
    def setUp(self):
        # Ensure no stale singletons bleed between tests
        import sovereign.models.dispatcher as dm
        dm._dispatcher = None
        from sovereign.models.dispatcher import ProviderDispatcher
        self.dispatcher = ProviderDispatcher()

    def test_build_all_providers(self):
        for pid in ("anthropic", "openai", "gemini", "perplexity", "qwen", "local"):
            p = self.dispatcher._get(pid)
            self.assertIsNotNone(p)

    def test_build_unknown_provider_falls_back_to_local(self):
        p = self.dispatcher._build("nonexistent")
        from sovereign.models.local_provider import LocalProvider
        self.assertIsInstance(p, LocalProvider)

    def test_providers_are_cached(self):
        p1 = self.dispatcher._get("openai")
        p2 = self.dispatcher._get("openai")
        self.assertIs(p1, p2)

    def test_complete_routes_to_provider(self):
        from sovereign.models.base_provider import CompletionRequest, CompletionResponse

        mock_resp = CompletionResponse(content="hi", model="gpt-4o-mini", provider="openai")
        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=mock_resp)
        mock_provider.record_error = MagicMock()
        self.dispatcher._providers["openai"] = mock_provider

        req = CompletionRequest(messages=[{"role": "user", "content": "test"}])
        resp = asyncio.run(self.dispatcher.complete("openai", "gpt-4o-mini", req))
        self.assertEqual(resp.content, "hi")

    def test_complete_returns_stub_on_exception(self):
        from sovereign.models.base_provider import CompletionRequest

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(side_effect=RuntimeError("fail"))
        mock_provider.record_error = MagicMock()
        self.dispatcher._providers["gemini"] = mock_provider

        req = CompletionRequest(messages=[{"role": "user", "content": "test"}])
        resp = asyncio.run(self.dispatcher.complete("gemini", "gemini-1.5-flash", req))
        self.assertIn("gemini error", resp.content)

    def test_stream_yields_tokens(self):
        from sovereign.models.base_provider import CompletionRequest

        async def fake_stream():
            yield "tok1"
            yield "tok2"

        mock_provider = MagicMock()
        mock_provider.stream = MagicMock(return_value=fake_stream())
        mock_provider.record_success = MagicMock()
        mock_provider.record_error = MagicMock()
        self.dispatcher._providers["perplexity"] = mock_provider

        req = CompletionRequest(messages=[{"role": "user", "content": "test"}])
        async def collect():
            tokens = []
            async for t in self.dispatcher.stream("perplexity", "sonar", req):
                tokens.append(t)
            return tokens
        tokens = asyncio.run(collect())
        self.assertIn("tok1", tokens)
        self.assertIn("tok2", tokens)

    def test_stream_yields_error_on_exception(self):
        from sovereign.models.base_provider import CompletionRequest

        async def bad_stream():
            raise RuntimeError("stream fail")
            yield  # make it a generator

        mock_provider = MagicMock()
        mock_provider.stream = MagicMock(return_value=bad_stream())
        mock_provider.record_error = MagicMock()
        self.dispatcher._providers["openai"] = mock_provider

        req = CompletionRequest(messages=[{"role": "user", "content": "test"}])
        async def collect():
            tokens = []
            async for t in self.dispatcher.stream("openai", "gpt-4o-mini", req):
                tokens.append(t)
            return tokens
        tokens = asyncio.run(collect())
        self.assertTrue(any("stream error" in t for t in tokens))

    def test_health_check_delegates(self):
        from sovereign.models.base_provider import ProviderStatus

        mock_provider = MagicMock()
        mock_provider.health_check = AsyncMock(return_value=ProviderStatus.AVAILABLE)
        self.dispatcher._providers["anthropic"] = mock_provider

        status = asyncio.run(self.dispatcher.health_check("anthropic"))
        self.assertEqual(status, ProviderStatus.AVAILABLE)

    def test_health_report(self):
        from sovereign.models.base_provider import ProviderStatus

        mock_provider = MagicMock()
        mock_provider._status = ProviderStatus.DEGRADED
        self.dispatcher._providers["qwen"] = mock_provider

        report = self.dispatcher.health_report()
        self.assertEqual(report["qwen"], "degraded")

    def test_get_dispatcher_singleton(self):
        import sovereign.models.dispatcher as dm
        dm._dispatcher = None
        d1 = dm.get_dispatcher()
        d2 = dm.get_dispatcher()
        self.assertIs(d1, d2)


# ---------------------------------------------------------------------------
# GeminiProvider — API key in header (security fix)
# ---------------------------------------------------------------------------

class TestGeminiHeaderAuth(unittest.TestCase):
    def setUp(self):
        os.environ["GEMINI_API_KEY"] = "test-gemini-key"
        from sovereign.models.gemini_provider import GeminiProvider
        self.provider = GeminiProvider()

    def tearDown(self):
        os.environ.pop("GEMINI_API_KEY", None)

    def test_url_does_not_contain_api_key(self):
        url = self.provider._url("gemini-1.5-flash")
        self.assertNotIn("test-gemini-key", url)
        self.assertNotIn("key=", url)

    def test_headers_contain_api_key(self):
        headers = self.provider._headers()
        self.assertEqual(headers["X-Goog-Api-Key"], "test-gemini-key")


# ---------------------------------------------------------------------------
# KimiProvider
# ---------------------------------------------------------------------------

class TestKimiProviderNoKey(unittest.TestCase):
    def setUp(self):
        os.environ.pop("MOONSHOT_API_KEY", None)
        from sovereign.models.kimi_provider import KimiProvider
        self.provider = KimiProvider()

    def test_status_unavailable_without_key(self):
        from sovereign.models.base_provider import ProviderStatus
        self.assertEqual(self.provider._status, ProviderStatus.UNAVAILABLE)

    def test_complete_stub_without_key(self):
        from sovereign.models.base_provider import CompletionRequest
        req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
        resp = asyncio.run(self.provider.complete(req))
        self.assertIn("Kimi unavailable", resp.content)
        self.assertEqual(resp.provider, "kimi")

    def test_stream_stub_without_key(self):
        from sovereign.models.base_provider import CompletionRequest
        req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
        async def collect():
            tokens = []
            async for t in self.provider.stream(req):
                tokens.append(t)
            return tokens
        tokens = asyncio.run(collect())
        self.assertTrue(any("Kimi unavailable" in t for t in tokens))

    def test_health_check_unavailable(self):
        from sovereign.models.base_provider import ProviderStatus
        status = asyncio.run(self.provider.health_check())
        self.assertEqual(status, ProviderStatus.UNAVAILABLE)

    def test_estimate_cost_known_model(self):
        from sovereign.models.kimi_provider import KimiProvider
        cost = KimiProvider.estimate_cost("moonshot-v1-32k", 1_000_000, 1_000_000)
        self.assertGreater(cost, 0.0)

    def test_estimate_cost_unknown_model(self):
        from sovereign.models.kimi_provider import KimiProvider
        cost = KimiProvider.estimate_cost("unknown-kimi", 100, 100)
        self.assertEqual(cost, 0.0)

    def test_estimate_cost_thinking_model_premium(self):
        from sovereign.models.kimi_provider import KimiProvider
        cost_thinking = KimiProvider.estimate_cost("kimi-thinking-preview", 1_000_000, 1_000_000)
        cost_regular = KimiProvider.estimate_cost("kimi-latest", 1_000_000, 1_000_000)
        self.assertGreater(cost_thinking, cost_regular)


class TestKimiProviderWithKey(unittest.TestCase):
    def setUp(self):
        os.environ["MOONSHOT_API_KEY"] = "sk-test-moonshot-key"
        from sovereign.models.kimi_provider import KimiProvider
        self.provider = KimiProvider()

    def tearDown(self):
        os.environ.pop("MOONSHOT_API_KEY", None)

    def test_status_available_with_key(self):
        from sovereign.models.base_provider import ProviderStatus
        self.assertEqual(self.provider._status, ProviderStatus.AVAILABLE)

    def test_headers_bearer_token(self):
        headers = self.provider._headers()
        self.assertIn("Bearer sk-test-moonshot-key", headers["Authorization"])

    def test_build_body_with_system(self):
        from sovereign.models.base_provider import CompletionRequest
        req = CompletionRequest(
            messages=[{"role": "user", "content": "hi"}],
            system="You are helpful",
            model="moonshot-v1-32k",
        )
        body = self.provider._build_body(req)
        self.assertEqual(body["messages"][0]["role"], "system")
        self.assertEqual(body["model"], "moonshot-v1-32k")
        self.assertFalse(body["stream"])

    def test_build_body_stream_flag(self):
        from sovereign.models.base_provider import CompletionRequest
        req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
        body = self.provider._build_body(req, stream=True)
        self.assertTrue(body["stream"])

    def test_complete_success(self):
        from sovereign.models.base_provider import CompletionRequest
        mock_data = {
            "choices": [{"message": {"content": "ciao"}, "finish_reason": "stop"}],
            "model": "moonshot-v1-32k",
            "usage": {"prompt_tokens": 8, "completion_tokens": 3},
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_data
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            MockClient.return_value = mock_client

            req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
            resp = asyncio.run(self.provider.complete(req))

        self.assertEqual(resp.content, "ciao")
        self.assertEqual(resp.input_tokens, 8)
        self.assertEqual(resp.output_tokens, 3)
        self.assertEqual(resp.provider, "kimi")

    def test_complete_records_error_on_exception(self):
        from sovereign.models.base_provider import CompletionRequest
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=RuntimeError("timeout"))
            MockClient.return_value = mock_client

            req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
            with self.assertRaises(RuntimeError):
                asyncio.run(self.provider.complete(req))
        self.assertEqual(self.provider._error_count, 1)

    def test_stream_success(self):
        from sovereign.models.base_provider import CompletionRequest
        sse_lines = [
            'data: {"choices":[{"delta":{"content":"ciao"},"finish_reason":null}]}',
            'data: {"choices":[{"delta":{"content":" mondo"},"finish_reason":null}]}',
            "data: [DONE]",
        ]

        async def fake_aiter_lines():
            for line in sse_lines:
                yield line

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.aiter_lines = fake_aiter_lines
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_client = MagicMock()
        mock_client.stream = MagicMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
            async def collect():
                tokens = []
                async for t in self.provider.stream(req):
                    tokens.append(t)
                return tokens
            tokens = asyncio.run(collect())

        self.assertIn("ciao", tokens)
        self.assertIn(" mondo", tokens)

    def test_dispatcher_routes_to_kimi(self):
        from sovereign.models.base_provider import CompletionRequest, CompletionResponse
        from sovereign.models.dispatcher import ProviderDispatcher

        d = ProviderDispatcher()
        mock_resp = CompletionResponse(content="kimi!", model="kimi-latest", provider="kimi")
        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=mock_resp)
        mock_provider.record_error = MagicMock()
        d._providers["kimi"] = mock_provider

        req = CompletionRequest(messages=[{"role": "user", "content": "test"}])
        resp = asyncio.run(d.complete("kimi", "kimi-latest", req))
        self.assertEqual(resp.content, "kimi!")
        self.assertEqual(resp.provider, "kimi")


# ── ProviderIntentParser ───────────────────────────────────────────────────────

def test_provider_intent_openai():
    from sovereign.input_fabric.provider_intent import parse_provider_intent
    r = parse_provider_intent("usa GPT-4o per questa analisi")
    assert r.detected is True
    assert r.preferred_provider == "openai"
    assert r.preferred_model == "gpt-4o"

def test_provider_intent_kimi():
    from sovereign.input_fabric.provider_intent import parse_provider_intent
    r = parse_provider_intent("rispondi con Kimi")
    assert r.preferred_provider == "kimi"

def test_provider_intent_gemini_flash():
    from sovereign.input_fabric.provider_intent import parse_provider_intent
    r = parse_provider_intent("voglio usare Gemini Flash")
    assert r.preferred_provider == "gemini"
    assert r.preferred_model == "gemini-1.5-flash"

def test_provider_intent_mode_override():
    from sovereign.input_fabric.provider_intent import parse_provider_intent
    r = parse_provider_intent("attiva modalità caveman")
    assert r.mode_override == "caveman"
    assert r.preferred_provider is None

def test_provider_intent_no_match():
    from sovereign.input_fabric.provider_intent import parse_provider_intent
    r = parse_provider_intent("analizza il mio portafoglio crypto")
    assert r.detected is False
    assert r.preferred_provider is None

def test_provider_intent_claude_opus():
    from sovereign.input_fabric.provider_intent import parse_provider_intent
    r = parse_provider_intent("use Claude Opus for this")
    assert r.preferred_provider == "anthropic"
    assert "opus" in r.preferred_model

def test_pipeline_output_has_provider_fields():
    from sovereign.input_fabric.pipeline import PipelineOutput
    out = PipelineOutput(normalized_text="test", preferred_provider="openai", preferred_model="gpt-4o")
    assert out.preferred_provider == "openai"
    assert out.preferred_model == "gpt-4o"
    assert out.mode_override is None


# ── TTSEngine ─────────────────────────────────────────────────────────────────

def test_tts_engine_no_keys():
    from sovereign.hud.tts_engine import TTSEngine
    e = TTSEngine()
    assert e.backend == "unavailable"
    assert e.available is False

def test_tts_engine_backend_property():
    from sovereign.hud.tts_engine import TTSEngine
    e = TTSEngine()
    assert e.backend in {"openai", "elevenlabs", "pyttsx3", "unavailable"}


@pytest.mark.asyncio
async def test_tts_engine_speak_unavailable():
    from sovereign.hud.tts_engine import TTSEngine
    e = TTSEngine()
    result = await e.speak("hello")
    assert result == b""

@pytest.mark.asyncio
async def test_tts_engine_speak_to_file_unavailable(tmp_path):
    from sovereign.hud.tts_engine import TTSEngine
    e = TTSEngine()
    ok = await e.speak_to_file("hello", tmp_path / "out.mp3")
    assert ok is False

def test_tts_engine_imports():
    from sovereign.hud import TTSEngine, VoiceCommandRecogniser
    assert TTSEngine is not None
    assert VoiceCommandRecogniser is not None

# ── MorningBrief ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_morning_brief_generate():
    from sovereign.reporting.morning_brief import generate_morning_brief
    data = {"date": "2026-05-12", "weather": "sunny", "tasks": ["task1"]}
    brief = await generate_morning_brief(data)
    assert isinstance(brief, str)
    assert len(brief) > 10

@pytest.mark.asyncio
async def test_morning_brief_run_no_tts():
    from sovereign.reporting.morning_brief import run_morning_brief
    result = await run_morning_brief({"date": "2026-05-12"}, speak=False)
    assert isinstance(result, str)


# ── AgentFeedbackRegistry ─────────────────────────────────────────────────────

def test_feedback_registry_empty(tmp_path):
    from sovereign.registries.agent_feedback import AgentFeedbackRegistry
    r = AgentFeedbackRegistry(path=tmp_path / "feedback.json")
    s = r.summary()
    assert s["total_feedback"] == 0
    assert s["agents_rated"] == 0

def test_feedback_registry_record(tmp_path):
    from sovereign.registries.agent_feedback import AgentFeedbackRegistry
    r = AgentFeedbackRegistry(path=tmp_path / "feedback.json")
    r.record("agent_x", "sess1", "task1", 1, "great")
    r.record("agent_x", "sess1", "task2", -1, "bad")
    assert r.agent_score("agent_x") == 0.0
    r.record("agent_y", "sess1", "task3", 1)
    tops = r.top_agents(1)
    assert tops[0]["agent_id"] == "agent_y"
    summary = r.summary()
    assert summary["total_feedback"] == 3
    assert summary["agents_rated"] == 2

def test_feedback_poor_agents(tmp_path):
    from sovereign.registries.agent_feedback import AgentFeedbackRegistry
    r = AgentFeedbackRegistry(path=tmp_path / "feedback.json")
    r.record("bad_agent", "s", "t", -1)
    r.record("bad_agent", "s", "t2", -1)
    poor = r.poor_agents(threshold=-0.1)
    assert any(p["agent_id"] == "bad_agent" for p in poor)
