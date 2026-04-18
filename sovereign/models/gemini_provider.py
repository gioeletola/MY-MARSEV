"""Google Gemini provider — uses httpx directly (no Google SDK dependency)."""
from __future__ import annotations

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

_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
_DEFAULT_MODEL = "gemini-1.5-flash"

# USD per 1M tokens: (input_price, output_price)
GEMINI_MODELS: dict[str, tuple[float, float]] = {
    "gemini-1.5-flash": (0.0, 0.0),    # free tier
    "gemini-1.5-pro":   (3.50, 10.50),
}


def _cost(model: str, input_tokens: int, output_tokens: int) -> float:
    prices = GEMINI_MODELS.get(model)
    if not prices:
        return 0.0
    return round(
        (input_tokens / 1_000_000) * prices[0]
        + (output_tokens / 1_000_000) * prices[1],
        6,
    )


def _to_gemini_messages(request: CompletionRequest) -> list[dict]:
    """Convert provider-agnostic messages to Gemini `contents` format."""
    contents: list[dict] = []
    for msg in request.messages:
        role = msg.get("role", "user")
        # Gemini uses "user" / "model" roles
        gemini_role = "model" if role == "assistant" else "user"
        contents.append({
            "role": gemini_role,
            "parts": [{"text": msg.get("content", "")}],
        })
    return contents


class GeminiProvider(BaseProvider):
    provider_id = "gemini"
    display_name = "Google Gemini"

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__()
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        if not self._api_key:
            logger.warning("GEMINI_API_KEY not set — GeminiProvider will return stubs")
            self._status = ProviderStatus.UNAVAILABLE

    def _url(self, model: str, action: str = "generateContent") -> str:
        return f"{_API_BASE}/{model}:{action}?key={self._api_key}"

    def _build_body(self, request: CompletionRequest) -> dict:
        body: dict = {
            "contents": _to_gemini_messages(request),
            "generationConfig": {
                "maxOutputTokens": request.max_tokens,
                "temperature": request.temperature,
            },
        }
        if request.system:
            body["systemInstruction"] = {
                "parts": [{"text": request.system}]
            }
        return body

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        if not self._api_key:
            return CompletionResponse(
                content="[Gemini unavailable: no API key]",
                model=request.model or _DEFAULT_MODEL,
                provider=self.provider_id,
            )

        model = request.model or _DEFAULT_MODEL
        t0 = time.monotonic()
        body = self._build_body(request)
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(self._url(model), json=body)
                resp.raise_for_status()

            data = resp.json()
            latency = (time.monotonic() - t0) * 1000.0
            self.record_success()

            candidate = data["candidates"][0]
            text = candidate["content"]["parts"][0].get("text", "")

            usage_meta = data.get("usageMetadata", {})
            input_tokens = usage_meta.get("promptTokenCount", 0)
            output_tokens = usage_meta.get("candidatesTokenCount", 0)
            stop_reason = candidate.get("finishReason", "STOP").lower()

            return CompletionResponse(
                content=text,
                model=model,
                provider=self.provider_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency,
                stop_reason=stop_reason,
                raw=data,
            )
        except Exception as exc:
            self.record_error()
            logger.error("GeminiProvider.complete error: %s", exc)
            raise

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:  # type: ignore[override]
        if not self._api_key:
            yield "[Gemini unavailable: no API key]"
            return

        model = request.model or _DEFAULT_MODEL
        body = self._build_body(request)
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    self._url(model, "streamGenerateContent"),
                    json=body,
                ) as resp:
                    resp.raise_for_status()
                    # Gemini streaming returns newline-delimited JSON objects
                    buffer = ""
                    async for chunk in resp.aiter_bytes():
                        buffer += chunk.decode("utf-8", errors="replace")
                        # Parse complete JSON objects from the buffer
                        while True:
                            try:
                                obj, idx = self._parse_first_json(buffer)
                                buffer = buffer[idx:]
                                parts = (
                                    obj.get("candidates", [{}])[0]
                                    .get("content", {})
                                    .get("parts", [])
                                )
                                for part in parts:
                                    text = part.get("text", "")
                                    if text:
                                        yield text
                            except (ValueError, KeyError):
                                break
            self.record_success()
        except Exception as exc:
            self.record_error()
            logger.error("GeminiProvider.stream error: %s", exc)
            raise

    @staticmethod
    def _parse_first_json(text: str) -> tuple[dict, int]:
        """
        Attempt to parse the first complete JSON object from *text*.
        Returns (parsed_dict, end_index) or raises ValueError.
        """
        import json

        depth = 0
        in_string = False
        escape = False
        start = text.find("{")
        if start == -1:
            raise ValueError("no JSON object found")
        for i, ch in enumerate(text[start:], start=start):
            if escape:
                escape = False
                continue
            if ch == "\\" and in_string:
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(text[start : i + 1]), i + 1
        raise ValueError("incomplete JSON object")

    async def health_check(self) -> ProviderStatus:
        if not self._api_key:
            return ProviderStatus.UNAVAILABLE
        return self._status

    @staticmethod
    def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
        return _cost(model, input_tokens, output_tokens)
