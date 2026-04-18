"""OpenAI API provider using httpx (no openai SDK needed)."""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

from sovereign.models.base_provider import (
    BaseProvider,
    CompletionRequest,
    CompletionResponse,
    ProviderStatus,
)

logger = logging.getLogger(__name__)

_CHAT_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIProvider(BaseProvider):
    """OpenAI API provider using httpx (no openai SDK needed)."""

    provider_id = "openai"
    display_name = "OpenAI GPT"

    MODELS: dict[str, dict[str, float]] = {
        "gpt-4o": {"input": 5.0, "output": 15.0},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "o1-mini": {"input": 3.0, "output": 12.0},
    }
    DEFAULT_MODEL = "gpt-4o-mini"

    def __init__(self, api_key: str = "") -> None:
        super().__init__()
        self._api_key: str = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # BaseProvider interface
    # ------------------------------------------------------------------

    async def complete(
        self,
        request: CompletionRequest | None = None,
        *,
        messages: list[dict[str, Any]] | None = None,
        model: str = "",
        max_tokens: int = 2048,
        stream: bool = False,
    ) -> dict[str, Any] | CompletionResponse:
        """Execute a completion.

        Accepts either a CompletionRequest (BaseProvider interface) or
        keyword arguments (standalone dict-returning mode).
        """
        if request is not None:
            # BaseProvider interface path
            return await self._complete_request(request)

        # Standalone dict-returning path
        return await self._complete_dict(
            messages=messages or [],
            model=model or self.DEFAULT_MODEL,
            max_tokens=max_tokens,
            stream=stream,
        )

    async def _complete_request(self, request: CompletionRequest) -> CompletionResponse:
        if not self._api_key:
            self.record_error()
            raise RuntimeError("OpenAI provider: no API key configured")

        model = request.model or self.DEFAULT_MODEL
        msgs: list[dict[str, Any]] = []
        if request.system:
            msgs.append({"role": "system", "content": request.system})
        msgs.extend(request.messages)

        payload: dict[str, Any] = {
            "model": model,
            "messages": msgs,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        t0 = time.monotonic()
        try:
            raw = await self._post(payload)
        except Exception as exc:
            self.record_error()
            logger.error("OpenAIProvider error: %s", exc)
            raise

        latency = (time.monotonic() - t0) * 1000.0
        self.record_success()

        choice = raw["choices"][0]
        usage = raw.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        return CompletionResponse(
            content=choice["message"].get("content") or "",
            model=raw.get("model", model),
            provider=self.provider_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency,
            stop_reason=choice.get("finish_reason") or "stop",
            raw=raw,
        )

    async def _complete_dict(
        self,
        messages: list[dict[str, Any]],
        model: str,
        max_tokens: int,
        stream: bool,  # noqa: ARG002  (streaming not implemented in dict path)
    ) -> dict[str, Any]:
        """Return a normalised dict response for standalone use."""
        if not self._api_key:
            return {"content": "", "error": "no_api_key"}

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        t0 = time.monotonic()
        try:
            raw = await self._post(payload)
        except Exception as exc:
            logger.error("OpenAIProvider dict error: %s", exc)
            return {"content": "", "error": str(exc)}

        latency = (time.monotonic() - t0) * 1000.0
        choice = raw["choices"][0]
        usage = raw.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        return {
            "content": choice["message"].get("content") or "",
            "model": raw.get("model", model),
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
            "cost_usd": self.estimate_cost(model, input_tokens, output_tokens),
            "provider": self.provider_id,
            "latency_ms": latency,
            "error": None,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        resp = await self._client.post(_CHAT_URL, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()  # type: ignore[return-value]

    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Return estimated cost in USD for the given token counts."""
        pricing = self.MODELS.get(model) or self.MODELS[self.DEFAULT_MODEL]
        return (
            input_tokens * pricing["input"] / 1_000_000
            + output_tokens * pricing["output"] / 1_000_000
        )

    async def health_check(self) -> ProviderStatus:
        if not self._api_key:
            return ProviderStatus.UNAVAILABLE
        return self._status

    @property
    def available(self) -> bool:
        """True if an API key is configured."""
        return bool(self._api_key)
