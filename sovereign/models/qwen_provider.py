"""
Qwen local provider — runs Qwen models via Ollama or a vLLM-compatible endpoint.

Supports:
  - qwen2.5 (7B, 14B, 32B, 72B)
  - qwen2.5-coder (7B, 14B)
  - qwen3 (8B, 14B, 32B)

Endpoint: Ollama (http://localhost:11434) or vLLM OpenAI-compat (http://localhost:8000)
"""
from __future__ import annotations

import logging
import time
from typing import AsyncIterator

import httpx

from sovereign.models.base_provider import (
    BaseProvider, CompletionRequest, CompletionResponse, ProviderStatus,
)

logger = logging.getLogger(__name__)

_DEFAULT_OLLAMA_URL = "http://localhost:11434"
_DEFAULT_VLLM_URL   = "http://localhost:8000"
_DEFAULT_MODEL      = "qwen2.5:7b"

QWEN_MODELS: dict[str, dict] = {
    # model_id: {context, description, tier}
    "qwen2.5:7b":        {"context": 131_072, "tier": "fast",     "description": "Qwen 2.5 7B — fast, low VRAM"},
    "qwen2.5:14b":       {"context": 131_072, "tier": "balanced", "description": "Qwen 2.5 14B — balanced capability"},
    "qwen2.5:32b":       {"context": 131_072, "tier": "balanced", "description": "Qwen 2.5 32B — strong reasoning"},
    "qwen2.5:72b":       {"context": 131_072, "tier": "frontier", "description": "Qwen 2.5 72B — near-frontier"},
    "qwen2.5-coder:7b":  {"context":  32_768, "tier": "fast",     "description": "Qwen 2.5 Coder 7B — code tasks"},
    "qwen2.5-coder:14b": {"context":  32_768, "tier": "balanced", "description": "Qwen 2.5 Coder 14B — code tasks"},
    "qwen3:8b":          {"context": 131_072, "tier": "fast",     "description": "Qwen 3 8B — latest generation"},
    "qwen3:14b":         {"context": 131_072, "tier": "balanced", "description": "Qwen 3 14B — latest generation"},
    "qwen3:32b":         {"context": 131_072, "tier": "frontier", "description": "Qwen 3 32B — frontier-class local"},
}

_TIER_DEFAULT: dict[str, str] = {
    "fast":     "qwen2.5:7b",
    "balanced": "qwen2.5:14b",
    "frontier": "qwen3:32b",
}


class QwenProvider(BaseProvider):
    """
    Runs Qwen models locally.

    backend="ollama"  → POST /api/chat   (Ollama native)
    backend="vllm"    → POST /v1/chat/completions  (OpenAI-compatible)
    """

    provider_id   = "qwen"
    display_name  = "Qwen (Local)"

    def __init__(
        self,
        model: str = _DEFAULT_MODEL,
        backend: str = "ollama",
        base_url: str = "",
    ) -> None:
        super().__init__()
        self._default_model = model
        self._backend = backend
        if not base_url:
            base_url = _DEFAULT_VLLM_URL if backend == "vllm" else _DEFAULT_OLLAMA_URL
        self._base_url = base_url.rstrip("/")
        self._http = httpx.AsyncClient(base_url=self._base_url, timeout=180.0)

    # ------------------------------------------------------------------

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        model = request.model or self._default_model
        t0 = time.monotonic()
        try:
            if self._backend == "vllm":
                return await self._complete_vllm(request, model, t0)
            return await self._complete_ollama(request, model, t0)
        except httpx.ConnectError:
            self.record_error()
            logger.warning("QwenProvider: cannot connect to %s (model=%s)", self._base_url, model)
            return CompletionResponse(
                content="[Qwen offline — cannot connect]",
                model=model, provider=self.provider_id,
                stop_reason="error",
            )
        except Exception as exc:
            self.record_error()
            logger.error("QwenProvider error: %s", exc)
            return CompletionResponse(
                content=f"[Qwen error: {exc}]",
                model=model, provider=self.provider_id,
                stop_reason="error",
            )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        resp = await self.complete(request)
        yield resp.content

    async def health_check(self) -> ProviderStatus:
        try:
            if self._backend == "vllm":
                r = await self._http.get("/health", timeout=3.0)
            else:
                r = await self._http.get("/api/tags", timeout=3.0)
            if r.status_code < 400:
                self._status = ProviderStatus.AVAILABLE
                return ProviderStatus.AVAILABLE
        except Exception:
            pass
        self._status = ProviderStatus.UNAVAILABLE
        return ProviderStatus.UNAVAILABLE

    # ------------------------------------------------------------------

    async def _complete_ollama(
        self, request: CompletionRequest, model: str, t0: float
    ) -> CompletionResponse:
        messages = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.extend(request.messages)
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }
        resp = await self._http.post("/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        latency = (time.monotonic() - t0) * 1000.0
        self.record_success()
        return CompletionResponse(
            content=data.get("message", {}).get("content", ""),
            model=model,
            provider=self.provider_id,
            input_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0),
            latency_ms=latency,
            stop_reason=data.get("done_reason", "stop"),
        )

    async def _complete_vllm(
        self, request: CompletionRequest, model: str, t0: float
    ) -> CompletionResponse:
        messages = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.extend(request.messages)
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": False,
        }
        resp = await self._http.post("/v1/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()
        latency = (time.monotonic() - t0) * 1000.0
        self.record_success()
        choice = data.get("choices", [{}])[0]
        usage = data.get("usage", {})
        return CompletionResponse(
            content=choice.get("message", {}).get("content", ""),
            model=data.get("model", model),
            provider=self.provider_id,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            latency_ms=latency,
            stop_reason=choice.get("finish_reason", "stop"),
        )

    # ------------------------------------------------------------------

    @classmethod
    def default_for_tier(cls, tier: str = "balanced") -> "QwenProvider":
        """Convenience constructor: picks the right default model for a tier."""
        model = _TIER_DEFAULT.get(tier, _DEFAULT_MODEL)
        return cls(model=model)

    @classmethod
    def available_models(cls) -> list[str]:
        return list(QWEN_MODELS.keys())
