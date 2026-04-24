"""
OpenAI-compatible engine adapter.

Works with: OpenAI, Azure OpenAI, vLLM, LM Studio, LocalAI, Groq, Together AI,
or any server implementing the /v1/chat/completions endpoint.
"""
from __future__ import annotations

import os
import time
from typing import Any, AsyncIterator

from sovereign.engine.base import (
    BaseEngine, CompletionRequest, CompletionResponse, EngineHealth, EngineStatus,
)

_OPENAI_MODELS = {"gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"}
_GEMINI_MODELS = {"gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0-flash"}


class OpenAICompatEngine(BaseEngine):
    engine_id = "openai_compat"
    engine_name = "OpenAI-Compatible"
    supports_streaming = True
    supports_tool_use = True
    is_local = False

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._api_key = self._config.get("api_key") or os.getenv("OPENAI_API_KEY", "")
        self._base_url = self._config.get("base_url") or os.getenv(
            "OPENAI_BASE_URL", "https://api.openai.com/v1"
        )
        self._provider = self._config.get("provider", "openai")
        self._extra_models: set[str] = set(self._config.get("extra_models", []))
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
        return self._client

    def supports_model(self, model_id: str) -> bool:
        return (
            model_id in _OPENAI_MODELS
            or model_id in _GEMINI_MODELS
            or model_id in self._extra_models
        )

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        client = self._get_client()
        t0 = time.monotonic()

        messages = list(request.messages)
        if request.system:
            messages = [{"role": "system", "content": request.system}] + messages

        kwargs: dict[str, Any] = {
            "model": request.model_id,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.tools:
            # Convert Anthropic tool format → OpenAI format if needed
            kwargs["tools"] = [
                {"type": "function", "function": t}
                if "function" not in t else t
                for t in request.tools
            ]

        try:
            response = await client.chat.completions.create(**kwargs)
        except Exception as exc:
            latency_ms = (time.monotonic() - t0) * 1000
            return CompletionResponse(
                model_id=request.model_id,
                content=f"[OpenAICompatEngine error: {exc}]",
                finish_reason="error",
                latency_ms=latency_ms,
            )

        latency_ms = (time.monotonic() - t0) * 1000
        choice = response.choices[0]
        msg = choice.message

        content = msg.content or ""
        tool_calls: list[dict] = []
        if msg.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "input": tc.function.arguments,
                }
                for tc in msg.tool_calls
            ]

        usage = response.usage
        return CompletionResponse(
            model_id=request.model_id,
            content=content,
            finish_reason=choice.finish_reason or "stop",
            tool_calls=tool_calls,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            latency_ms=latency_ms,
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        client = self._get_client()

        messages = list(request.messages)
        if request.system:
            messages = [{"role": "system", "content": request.system}] + messages

        try:
            stream = await client.chat.completions.create(
                model=request.model_id,
                messages=messages,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    yield delta
        except Exception as exc:
            yield f"[OpenAICompatEngine stream error: {exc}]"

    async def health(self) -> EngineHealth:
        if not self._api_key:
            return EngineHealth(
                engine_id=self.engine_id,
                status=EngineStatus.UNAVAILABLE,
                error=f"{self._provider.upper()}_API_KEY not set",
            )
        try:
            t0 = time.monotonic()
            client = self._get_client()
            models_page = await client.models.list()
            latency_ms = (time.monotonic() - t0) * 1000
            available = [m.id for m in models_page.data]
            return EngineHealth(
                engine_id=self.engine_id,
                status=EngineStatus.AVAILABLE,
                available_models=available,
                latency_ms=latency_ms,
            )
        except Exception as exc:
            return EngineHealth(
                engine_id=self.engine_id,
                status=EngineStatus.UNAVAILABLE,
                error=str(exc),
            )


class GeminiEngine(OpenAICompatEngine):
    """Gemini via OpenAI-compatible endpoint (Google AI Studio)."""
    engine_id = "gemini"
    engine_name = "Google Gemini"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        cfg = dict(config or {})
        cfg.setdefault("api_key", os.getenv("GOOGLE_API_KEY", ""))
        cfg.setdefault("base_url", "https://generativelanguage.googleapis.com/v1beta/openai/")
        cfg["provider"] = "gemini"
        super().__init__(cfg)

    def supports_model(self, model_id: str) -> bool:
        return model_id in _GEMINI_MODELS or model_id.startswith("gemini-")
