"""OpenAI provider stub — requires 'openai' package (optional dependency)."""
from __future__ import annotations

import logging
import time

from sovereign.models.base_provider import (
    BaseProvider, CompletionRequest, CompletionResponse, ProviderStatus
)

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gpt-4o"


class OpenAIProvider(BaseProvider):
    provider_id = "openai"
    display_name = "OpenAI GPT"

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__()
        self._api_key = api_key
        self._client = None
        self._available = False
        try:
            import openai
            self._client = openai.AsyncOpenAI(api_key=api_key)
            self._available = True
        except ImportError:
            logger.warning("openai package not installed — OpenAIProvider unavailable")
            self._status = ProviderStatus.UNAVAILABLE

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        if not self._available or self._client is None:
            raise RuntimeError("OpenAI provider unavailable (package not installed)")

        model = request.model or _DEFAULT_MODEL
        t0 = time.monotonic()
        try:
            messages = []
            if request.system:
                messages.append({"role": "system", "content": request.system})
            messages.extend(request.messages)

            resp = await self._client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
            )
            latency = (time.monotonic() - t0) * 1000.0
            self.record_success()

            choice = resp.choices[0]
            return CompletionResponse(
                content=choice.message.content or "",
                model=model,
                provider=self.provider_id,
                input_tokens=resp.usage.prompt_tokens if resp.usage else 0,
                output_tokens=resp.usage.completion_tokens if resp.usage else 0,
                latency_ms=latency,
                stop_reason=choice.finish_reason or "stop",
                raw=resp,
            )
        except Exception as exc:
            self.record_error()
            logger.error("OpenAIProvider error: %s", exc)
            raise

    async def health_check(self) -> ProviderStatus:
        if not self._available:
            return ProviderStatus.UNAVAILABLE
        return self._status
