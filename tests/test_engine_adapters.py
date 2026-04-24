"""Tests for sovereign/engine/ adapters."""
from __future__ import annotations

import pytest
from unittest.mock import patch

from sovereign.engine.base import (
    BaseEngine, CompletionRequest, CompletionResponse, EngineHealth, EngineStatus,
)
from sovereign.engine.multi import MultiEngine
from sovereign.engine.ollama import OllamaEngine
from sovereign.engine.qwen_local import QwenLocalEngine
from sovereign.engine.openai_compat import OpenAICompatEngine, GeminiEngine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _request(model_id: str = "test-model") -> CompletionRequest:
    return CompletionRequest(
        model_id=model_id,
        messages=[{"role": "user", "content": "Hello"}],
        system="You are a test assistant.",
    )


class _StubEngine(BaseEngine):
    engine_id = "stub"
    engine_name = "Stub"

    def __init__(self, model_ids: list[str], *, available: bool = True):
        super().__init__()
        self._model_ids = model_ids
        self._available = available

    def supports_model(self, model_id: str) -> bool:
        return model_id in self._model_ids

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        return CompletionResponse(
            model_id=request.model_id,
            content="stub response",
            input_tokens=10,
            output_tokens=5,
        )

    async def health(self) -> EngineHealth:
        status = EngineStatus.AVAILABLE if self._available else EngineStatus.UNAVAILABLE
        return EngineHealth(
            engine_id=self.engine_id,
            status=status,
            available_models=self._model_ids,
        )


# ---------------------------------------------------------------------------
# CompletionRequest / CompletionResponse
# ---------------------------------------------------------------------------

def test_completion_response_total_tokens():
    resp = CompletionResponse(
        model_id="m", content="hi", input_tokens=100, output_tokens=50
    )
    assert resp.total_tokens == 150


def test_completion_request_defaults():
    req = _request()
    assert req.max_tokens == 4096
    assert req.temperature == 0.7
    assert req.tools == []
    assert req.stream is False


# ---------------------------------------------------------------------------
# MultiEngine
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multi_engine_routes_correct():
    eng_a = _StubEngine(["model-a"])
    eng_b = _StubEngine(["model-b"])
    multi = MultiEngine([eng_a, eng_b])

    resp_a = await multi.complete(_request("model-a"))
    assert resp_a.content == "stub response"

    resp_b = await multi.complete(_request("model-b"))
    assert resp_b.content == "stub response"


@pytest.mark.asyncio
async def test_multi_engine_fallback_when_no_match():
    eng = _StubEngine(["model-x"])
    multi = MultiEngine([eng])
    # Requesting an unknown model falls back to first engine
    resp = await multi.complete(_request("unknown-model"))
    assert resp.content == "stub response"


@pytest.mark.asyncio
async def test_multi_engine_empty_returns_error():
    multi = MultiEngine([])
    resp = await multi.complete(_request("any"))
    assert "no engines" in resp.content.lower()
    assert resp.finish_reason == "error"


@pytest.mark.asyncio
async def test_multi_engine_health_aggregates():
    eng_a = _StubEngine(["a"], available=True)
    eng_b = _StubEngine(["b"], available=False)
    multi = MultiEngine([eng_a, eng_b])
    h = await multi.health()
    assert h.status == EngineStatus.AVAILABLE
    assert "a" in h.available_models


@pytest.mark.asyncio
async def test_multi_engine_health_all_down():
    eng = _StubEngine(["x"], available=False)
    multi = MultiEngine([eng])
    h = await multi.health()
    assert h.status == EngineStatus.UNAVAILABLE


def test_multi_engine_supports_model():
    multi = MultiEngine([_StubEngine(["alpha"]), _StubEngine(["beta"])])
    assert multi.supports_model("alpha")
    assert multi.supports_model("beta")
    assert not multi.supports_model("gamma")


@pytest.mark.asyncio
async def test_multi_engine_stream():
    multi = MultiEngine([_StubEngine(["m"])])
    chunks = []
    async for chunk in multi.stream(_request("m")):
        chunks.append(chunk)
    assert "".join(chunks) == "stub response"


def test_multi_engine_add_engine():
    multi = MultiEngine([])
    assert len(multi.engines()) == 0
    multi.add_engine(_StubEngine(["new"]))
    assert len(multi.engines()) == 1
    assert multi.supports_model("new")


# ---------------------------------------------------------------------------
# OllamaEngine
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ollama_supports_any_model():
    engine = OllamaEngine()
    assert engine.supports_model("any-model-name")
    assert engine.is_local is True


@pytest.mark.asyncio
async def test_ollama_health_unavailable_when_offline():
    engine = OllamaEngine({"host": "http://localhost:99999"})
    h = await engine.health()
    assert h.status == EngineStatus.UNAVAILABLE
    assert h.error is not None


@pytest.mark.asyncio
async def test_ollama_complete_returns_error_on_connection_failure():
    engine = OllamaEngine({"host": "http://localhost:99999"})
    resp = await engine.complete(_request("qwen2.5:7b"))
    assert "error" in resp.content.lower()
    assert resp.finish_reason == "error"


# ---------------------------------------------------------------------------
# QwenLocalEngine
# ---------------------------------------------------------------------------

def test_qwen_supports_qwen_models():
    engine = QwenLocalEngine()
    assert engine.supports_model("qwen3:32b")
    assert engine.supports_model("qwen2.5:14b")
    assert engine.supports_model("qwen2.5-coder:14b")


@pytest.mark.asyncio
async def test_qwen_health_filters_to_qwen():
    # health() filters available_models to Qwen only
    engine = QwenLocalEngine({"host": "http://localhost:99999"})

    async def _stub_super_health(self):
        from sovereign.engine.base import EngineHealth, EngineStatus
        return EngineHealth(
            engine_id="ollama",
            status=EngineStatus.AVAILABLE,
            available_models=["qwen2.5:7b", "mistral:7b", "llama3:8b"],
        )

    with patch.object(OllamaEngine, "health", _stub_super_health):
        h = await engine.health()
    assert "qwen2.5:7b" in h.available_models
    assert "mistral:7b" not in h.available_models


# ---------------------------------------------------------------------------
# OpenAICompatEngine
# ---------------------------------------------------------------------------

def test_openai_compat_supports_openai_models():
    engine = OpenAICompatEngine()
    assert engine.supports_model("gpt-4o")
    assert engine.supports_model("gpt-4o-mini")


def test_openai_compat_supports_extra_models():
    engine = OpenAICompatEngine({"extra_models": ["my-custom-model"]})
    assert engine.supports_model("my-custom-model")


@pytest.mark.asyncio
async def test_openai_compat_health_no_key():
    engine = OpenAICompatEngine({"api_key": ""})
    # Without a key the env might have one; force empty
    import os
    old = os.environ.pop("OPENAI_API_KEY", None)
    try:
        engine._api_key = ""
        h = await engine.health()
        assert h.status == EngineStatus.UNAVAILABLE
    finally:
        if old is not None:
            os.environ["OPENAI_API_KEY"] = old


def test_gemini_engine_supports_gemini_models():
    engine = GeminiEngine()
    assert engine.supports_model("gemini-1.5-pro")
    assert engine.supports_model("gemini-1.5-flash")
    assert engine.supports_model("gemini-2.0-flash")
