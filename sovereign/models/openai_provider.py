"""OpenAI provider — uses httpx directly (no openai SDK dependency)."""
from __future__ import annotations

import json
import logging
import os
import time

import httpx

from sovereign.models.base_provider import (
    BaseProvider,
    CompletionRequest,
    CompletionResponse,
    ProviderStatus,
)

logger = logging.getLogger(__name__)

_API_BASE = "https://api.openai.com/v1"
_DEFAULT_MODEL = "gpt-4o-mini"

# USD per 1M tokens: (input_price, output_price)
OPENAI_MODELS: dict[str, tuple[float, float]] = {
    "gpt-4o":       (5.00,  15.00),
    "gpt-4o-mini":  (0.15,   0.60),
    "o1-mini":      (3.00,  12.00),
}


def _cost(model: str, input_tokens: int, output_tokens: int) -> float:
    prices = OPENAI_MODELS.get(model)
    if not prices:
        return 0.0
    return round(
        (input_tokens / 1_000_000) * prices[0]
        + (output_tokens / 1_000_000) * prices[1],
        6,
    )


class OpenAIProvider(BaseProvider):
    provider_id = "openai"
    display_name = "OpenAI GPT"

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__()
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not self._api_key:
            logger.warning("OPENAI_API_KEY not set — OpenAIProvider will return stubs")
            self._status = ProviderStatus.UNAVAILABLE

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _build_body(self, request: CompletionRequest, stream: bool = False) -> dict:
        messages: list[dict] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.extend(request.messages)
        body: dict = {
            "model": request.model or _DEFAULT_MODEL,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": stream,
        }
        return body

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        if not self._api_key:
            return CompletionResponse(
                content="[OpenAI unavailable: no API key]",
                model=request.model or _DEFAULT_MODEL,
                provider=self.provider_id,
            )

        model = request.model or _DEFAULT_MODEL
        t0 = time.monotonic()
        body = self._build_body(request, stream=False)
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{_API_BASE}/chat/completions",
                    headers=self._headers(),
                    json=body,
                )
                resp.raise_for_status()

            data = resp.json()
            latency = (time.monotonic() - t0) * 1000.0
            self.record_success()

            choice = data["choices"][0]
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

            return CompletionResponse(
                content=choice["message"].get("content") or "",
                model=data.get("model", model),
                provider=self.provider_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency,
                stop_reason=choice.get("finish_reason") or "stop",
                raw=data,
            )
        except Exception as exc:
            self.record_error()
            logger.error("OpenAIProvider.complete error: %s", exc)
            raise

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:  # type: ignore[override]
        if not self._api_key:
            yield "[OpenAI unavailable: no API key]"
            return

        body = self._build_body(request, stream=True)
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{_API_BASE}/chat/completions",
                    headers=self._headers(),
                    json=body,
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        payload = line[6:]
                        if payload.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(payload)
                            delta = chunk["choices"][0].get("delta", {})
                            token = delta.get("content")
                            if token:
                                yield token
                        except (json.JSONDecodeError, KeyError):
                            continue
            self.record_success()
        except Exception as exc:
            self.record_error()
            logger.error("OpenAIProvider.stream error: %s", exc)
            raise

    async def health_check(self) -> ProviderStatus:
        if not self._api_key:
            return ProviderStatus.UNAVAILABLE
        return self._status

    @staticmethod
    def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
        return _cost(model, input_tokens, output_tokens)
