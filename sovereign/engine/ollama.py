"""
Ollama engine adapter — local model runner via Ollama REST API.
Endpoint: http://localhost:11434 (configurable via OLLAMA_HOST env var).
"""
from __future__ import annotations

import json
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

_DEFAULT_HOST = "http://localhost:11434"


class OllamaEngine(BaseEngine):
    engine_id = "ollama"
    engine_name = "Ollama (Local)"
    supports_streaming = True
    supports_tool_use = False
    is_local = True

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._host = (
            self._config.get("host")
            or os.getenv("OLLAMA_HOST", _DEFAULT_HOST)
        ).rstrip("/")

    def supports_model(self, model_id: str) -> bool:
        # Accept any model; Ollama resolves at runtime
        return True

    def _chat_url(self) -> str:
        return f"{self._host}/api/chat"

    def _tags_url(self) -> str:
        return f"{self._host}/api/tags"

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        import httpx
        t0 = time.monotonic()

        messages = list(request.messages)
        if request.system:
            messages = [{"role": "system", "content": request.system}] + messages

        payload = {
            "model": request.model_id,
            "messages": messages,
            "stream": False,
            "options": {"temperature": request.temperature},
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(self._chat_url(), json=payload)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            latency_ms = (time.monotonic() - t0) * 1000
            return CompletionResponse(
                model_id=request.model_id,
                content=f"[OllamaEngine error: {exc}]",
                finish_reason="error",
                latency_ms=latency_ms,
            )

        latency_ms = (time.monotonic() - t0) * 1000
        msg = data.get("message", {})
        return CompletionResponse(
            model_id=request.model_id,
            content=msg.get("content", ""),
            finish_reason=data.get("done_reason", "stop"),
            input_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0),
            latency_ms=latency_ms,
            raw=data,
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        import httpx

        messages = list(request.messages)
        if request.system:
            messages = [{"role": "system", "content": request.system}] + messages

        payload = {
            "model": request.model_id,
            "messages": messages,
            "stream": True,
            "options": {"temperature": request.temperature},
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", self._chat_url(), json=payload) as resp:
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                            delta = chunk.get("message", {}).get("content", "")
                            if delta:
                                yield delta
                            if chunk.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue
        except Exception as exc:
            yield f"[OllamaEngine stream error: {exc}]"

    async def health(self) -> EngineHealth:
        import httpx
        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(self._tags_url())
                latency_ms = (time.monotonic() - t0) * 1000
                if resp.status_code == 200:
                    models = [m["name"] for m in resp.json().get("models", [])]
                    return EngineHealth(
                        engine_id=self.engine_id,
                        status=EngineStatus.AVAILABLE,
                        available_models=models,
                        latency_ms=latency_ms,
                    )
        except Exception as exc:
            return EngineHealth(
                engine_id=self.engine_id,
                status=EngineStatus.UNAVAILABLE,
                error=str(exc),
            )
        return EngineHealth(engine_id=self.engine_id, status=EngineStatus.UNKNOWN)
