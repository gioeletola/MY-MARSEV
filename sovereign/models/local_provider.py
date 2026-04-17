"""Local model provider — bridges to Ollama or any OpenAI-compatible local endpoint."""
from __future__ import annotations

import logging
import time
from typing import AsyncIterator

import httpx

from sovereign.models.base_provider import (
    BaseProvider, CompletionRequest, CompletionResponse, ProviderStatus
)

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://localhost:11434"
_DEFAULT_MODEL = "llama3"


class LocalProvider(BaseProvider):
    """Talks to an Ollama-compatible local server via its OpenAI-compatible /v1 API."""

    provider_id = "local"
    display_name = "Local (Ollama)"

    def __init__(self, base_url: str = _DEFAULT_BASE_URL, model: str = _DEFAULT_MODEL) -> None:
        super().__init__()
        self._base_url = base_url.rstrip("/")
        self._default_model = model
        self._http = httpx.AsyncClient(base_url=self._base_url, timeout=120.0)

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        model = request.model or self._default_model
        t0 = time.monotonic()
        messages = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.extend(request.messages)

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": request.temperature},
        }
        try:
            resp = await self._http.post("/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            latency = (time.monotonic() - t0) * 1000.0
            self.record_success()
            content = data.get("message", {}).get("content", "")
            return CompletionResponse(
                content=content,
                model=model,
                provider=self.provider_id,
                input_tokens=data.get("prompt_eval_count", 0),
                output_tokens=data.get("eval_count", 0),
                latency_ms=latency,
                stop_reason=data.get("done_reason", "stop"),
                raw=data,
            )
        except Exception as exc:
            self.record_error()
            logger.error("LocalProvider error: %s", exc)
            raise

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        model = request.model or self._default_model
        messages = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.extend(request.messages)

        payload = {"model": model, "messages": messages, "stream": True}
        try:
            async with self._http.stream("POST", "/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        import json
                        chunk = json.loads(line)
                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            yield token
        except Exception as exc:
            self.record_error()
            logger.error("LocalProvider stream error: %s", exc)
            raise

    async def health_check(self) -> ProviderStatus:
        try:
            resp = await self._http.get("/api/tags", timeout=5.0)
            if resp.status_code == 200:
                self._status = ProviderStatus.AVAILABLE
            else:
                self._status = ProviderStatus.DEGRADED
        except Exception:
            self._status = ProviderStatus.UNAVAILABLE
        return self._status

    async def aclose(self) -> None:
        await self._http.aclose()
