"""Anthropic Claude provider — wraps the existing ClaudeClient with the BaseProvider interface."""
from __future__ import annotations

import time
import logging
from typing import AsyncIterator

import anthropic

from sovereign.models.base_provider import (
    BaseProvider, CompletionRequest, CompletionResponse, ProviderStatus
)

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "claude-sonnet-4-6"


class AnthropicProvider(BaseProvider):
    provider_id = "anthropic"
    display_name = "Anthropic Claude"

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__()
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        model = request.model or _DEFAULT_MODEL
        t0 = time.monotonic()
        try:
            kwargs: dict = dict(
                model=model,
                max_tokens=request.max_tokens,
                messages=request.messages,
            )
            if request.system:
                kwargs["system"] = request.system
            if request.tools:
                kwargs["tools"] = request.tools

            msg = await self._client.messages.create(**kwargs)
            latency = (time.monotonic() - t0) * 1000.0
            self.record_success()

            content = ""
            tool_calls: list = []
            for block in msg.content:
                if block.type == "text":
                    content += block.text
                elif block.type == "tool_use":
                    tool_calls.append({"id": block.id, "name": block.name, "input": block.input})

            usage = msg.usage
            return CompletionResponse(
                content=content,
                model=model,
                provider=self.provider_id,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
                cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
                latency_ms=latency,
                stop_reason=msg.stop_reason or "end_turn",
                tool_calls=tool_calls,
                raw=msg,
            )
        except anthropic.APIError as exc:
            self.record_error()
            logger.error("AnthropicProvider error: %s", exc)
            raise

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        model = request.model or _DEFAULT_MODEL
        kwargs: dict = dict(model=model, max_tokens=request.max_tokens, messages=request.messages)
        if request.system:
            kwargs["system"] = request.system

        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text

    async def health_check(self) -> ProviderStatus:
        return self._status
