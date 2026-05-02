"""Kimi (Moonshot AI) provider — OpenAI-compatible API.

Endpoint: https://api.moonshot.cn/v1
Auth:     MOONSHOT_API_KEY (Bearer token)
Docs:     https://platform.moonshot.cn/docs

Models:
  moonshot-v1-8k    — 8K  context, fast and cheap
  moonshot-v1-32k   — 32K context, balanced
  moonshot-v1-128k  — 128K context, long documents
  kimi-latest       — latest flagship (equivalent to 128k tier)
  kimi-thinking-preview — experimental extended thinking
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import AsyncIterator

import httpx

from sovereign.models.base_provider import (
    BaseProvider,
    CompletionRequest,
    CompletionResponse,
    ProviderStatus,
)

logger = logging.getLogger(__name__)

_API_BASE = "https://api.moonshot.cn/v1"
_DEFAULT_MODEL = "moonshot-v1-32k"

# USD per 1M tokens: (input_price, output_price)
# Converted from Moonshot's RMB pricing at ~7.25 CNY/USD
KIMI_MODELS: dict[str, tuple[float, float]] = {
    "moonshot-v1-8k":          (1.65,   1.65),
    "moonshot-v1-32k":         (3.30,   3.30),
    "moonshot-v1-128k":        (8.25,   8.25),
    "kimi-latest":             (8.25,   8.25),
    "kimi-thinking-preview":   (16.50, 16.50),  # extended thinking premium
}


def _cost(model: str, input_tokens: int, output_tokens: int) -> float:
    prices = KIMI_MODELS.get(model)
    if not prices:
        return 0.0
    return round(
        (input_tokens / 1_000_000) * prices[0]
        + (output_tokens / 1_000_000) * prices[1],
        6,
    )


class KimiProvider(BaseProvider):
    provider_id = "kimi"
    display_name = "Kimi (Moonshot AI)"

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__()
        self._api_key = api_key or os.environ.get("MOONSHOT_API_KEY", "")
        if not self._api_key:
            logger.warning("MOONSHOT_API_KEY not set — KimiProvider will return stubs")
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
        return {
            "model": request.model or _DEFAULT_MODEL,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": stream,
        }

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        if not self._api_key:
            return CompletionResponse(
                content="[Kimi unavailable: no MOONSHOT_API_KEY]",
                model=request.model or _DEFAULT_MODEL,
                provider=self.provider_id,
            )

        model = request.model or _DEFAULT_MODEL
        t0 = time.monotonic()
        body = self._build_body(request, stream=False)
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
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
            return CompletionResponse(
                content=choice["message"].get("content") or "",
                model=data.get("model", model),
                provider=self.provider_id,
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                latency_ms=latency,
                stop_reason=choice.get("finish_reason") or "stop",
                raw=data,
            )
        except Exception as exc:
            self.record_error()
            logger.error("KimiProvider.complete error: %s", exc)
            raise

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:  # type: ignore[override]
        if not self._api_key:
            yield "[Kimi unavailable: no MOONSHOT_API_KEY]"
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
            logger.error("KimiProvider.stream error: %s", exc)
            raise

    async def health_check(self) -> ProviderStatus:
        if not self._api_key:
            return ProviderStatus.UNAVAILABLE
        return self._status

    @staticmethod
    def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
        return _cost(model, input_tokens, output_tokens)
