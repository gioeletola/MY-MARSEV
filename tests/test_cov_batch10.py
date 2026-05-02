"""Coverage batch 10 — new model providers: Perplexity, ProviderDispatcher."""
from __future__ import annotations

import asyncio
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch


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
