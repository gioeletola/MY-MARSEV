"""
Cloud engine adapter — wraps the Anthropic SDK with prompt caching, tool use,
and streaming support. Falls back to OpenAI/Gemini via openai_compat.
"""
from __future__ import annotations

import os
import time
from typing import Any, AsyncIterator

from sovereign.engine.base import (
    BaseEngine,
    CompletionRequest,
    CompletionResponse,
    EngineHealth,
    EngineStatus,
)

_ANTHROPIC_MODELS = {
    "claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5-20251001",
}


class AnthropicEngine(BaseEngine):
    engine_id = "anthropic"
    engine_name = "Anthropic Claude"
    supports_streaming = True
    supports_tool_use = True
    is_local = False

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._api_key = self._config.get("api_key") or os.getenv("ANTHROPIC_API_KEY", "")
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            import anthropic
            self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
        return self._client

    def supports_model(self, model_id: str) -> bool:
        return model_id in _ANTHROPIC_MODELS

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        client = self._get_client()
        t0 = time.monotonic()

        kwargs: dict[str, Any] = {
            "model": request.model_id,
            "max_tokens": request.max_tokens,
            "messages": request.messages,
        }
        if request.system:
            kwargs["system"] = [
                {"type": "text", "text": request.system, "cache_control": {"type": "ephemeral"}},
            ]
        if request.tools:
            kwargs["tools"] = request.tools
        if request.tool_choice is not None:
            kwargs["tool_choice"] = request.tool_choice

        response = await client.messages.create(**kwargs)
        latency_ms = (time.monotonic() - t0) * 1000

        content = ""
        tool_calls: list[dict] = []
        for block in response.content:
            if block.type == "text":
                content = block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })

        usage = response.usage
        return CompletionResponse(
            model_id=request.model_id,
            content=content,
            finish_reason=response.stop_reason or "stop",
            tool_calls=tool_calls,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0),
            latency_ms=latency_ms,
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        client = self._get_client()

        kwargs: dict[str, Any] = {
            "model": request.model_id,
            "max_tokens": request.max_tokens,
            "messages": request.messages,
        }
        if request.system:
            kwargs["system"] = [
                {"type": "text", "text": request.system, "cache_control": {"type": "ephemeral"}},
            ]

        async with client.messages.stream(**kwargs) as stream_ctx:
            async for text in stream_ctx.text_stream:
                yield text

    async def health(self) -> EngineHealth:
        if not self._api_key:
            return EngineHealth(
                engine_id=self.engine_id,
                status=EngineStatus.UNAVAILABLE,
                error="ANTHROPIC_API_KEY not set",
            )
        try:
            t0 = time.monotonic()
            client = self._get_client()
            # Lightweight ping: list models (no token cost)
            await client.models.list()
            latency_ms = (time.monotonic() - t0) * 1000
            return EngineHealth(
                engine_id=self.engine_id,
                status=EngineStatus.AVAILABLE,
                available_models=list(_ANTHROPIC_MODELS),
                latency_ms=latency_ms,
            )
        except Exception as exc:
            return EngineHealth(
                engine_id=self.engine_id,
                status=EngineStatus.UNAVAILABLE,
                error=str(exc),
            )
