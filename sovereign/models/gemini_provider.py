<<<<<<< HEAD
"""Google Gemini API provider using httpx (no google-generativeai SDK needed)."""
=======
"""Google Gemini provider — uses httpx directly (no Google SDK dependency)."""
>>>>>>> b0c71f2 (feat(multi-provider+h24): OpenAI/Gemini providers, H24 worker pool, watchdog, health alerter, live integrations)
from __future__ import annotations

import logging
import os
import time
<<<<<<< HEAD
from typing import Any
=======
from typing import AsyncIterator
>>>>>>> b0c71f2 (feat(multi-provider+h24): OpenAI/Gemini providers, H24 worker pool, watchdog, health alerter, live integrations)

import httpx

from sovereign.models.base_provider import (
    BaseProvider,
    CompletionRequest,
    CompletionResponse,
    ProviderStatus,
)

logger = logging.getLogger(__name__)

<<<<<<< HEAD
_BASE_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)


class GeminiProvider(BaseProvider):
    """Google Gemini API provider using httpx (no google-generativeai SDK needed)."""

    provider_id = "gemini"
    display_name = "Google Gemini"

    MODELS: dict[str, dict[str, float]] = {
        # prices per 1M tokens (public Gemini 1.5 pricing)
        "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
        "gemini-1.5-pro": {"input": 3.50, "output": 10.50},
    }
    DEFAULT_MODEL = "gemini-1.5-flash"

    def __init__(self, api_key: str = "") -> None:
        super().__init__()
        self._api_key: str = api_key or os.environ.get("GEMINI_API_KEY", "")
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
            return await self._complete_request(request)

        return await self._complete_dict(
            messages=messages or [],
            model=model or self.DEFAULT_MODEL,
            max_tokens=max_tokens,
            stream=stream,
        )

    async def _complete_request(self, request: CompletionRequest) -> CompletionResponse:
        if not self._api_key:
            self.record_error()
            raise RuntimeError("Gemini provider: no API key configured")

        model = request.model or self.DEFAULT_MODEL
        contents = self._build_contents(request.system, request.messages)
        payload = self._build_payload(contents, request.max_tokens)

        t0 = time.monotonic()
        try:
            raw = await self._post(model, payload)
        except Exception as exc:
            self.record_error()
            logger.error("GeminiProvider error: %s", exc)
            raise

        latency = (time.monotonic() - t0) * 1000.0
        self.record_success()

        content, input_tokens, output_tokens = self._parse_response(raw)

        return CompletionResponse(
            content=content,
            model=model,
            provider=self.provider_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency,
            stop_reason=self._stop_reason(raw),
            raw=raw,
        )

    async def _complete_dict(
        self,
        messages: list[dict[str, Any]],
        model: str,
        max_tokens: int,
        stream: bool,  # noqa: ARG002
    ) -> dict[str, Any]:
        """Return a normalised dict response for standalone use."""
        if not self._api_key:
            return {"content": "", "error": "no_api_key"}

        contents = self._build_contents("", messages)
        payload = self._build_payload(contents, max_tokens)

        t0 = time.monotonic()
        try:
            raw = await self._post(model, payload)
        except Exception as exc:
            logger.error("GeminiProvider dict error: %s", exc)
            return {"content": "", "error": str(exc)}

        latency = (time.monotonic() - t0) * 1000.0
        content, input_tokens, output_tokens = self._parse_response(raw)

        return {
            "content": content,
            "model": model,
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
    # Message building helpers
    # ------------------------------------------------------------------

    def _build_contents(
        self,
        system: str,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Convert OpenAI-style messages to Gemini contents format."""
        contents: list[dict[str, Any]] = []
        if system:
            contents.append({"role": "user", "parts": [{"text": system}]})
            contents.append({"role": "model", "parts": [{"text": "Understood."}]})
        for msg in messages:
            role = "model" if msg.get("role") == "assistant" else "user"
            text = msg.get("content") or ""
            contents.append({"role": role, "parts": [{"text": text}]})
        return contents

    def _build_payload(
        self,
        contents: list[dict[str, Any]],
        max_tokens: int,
    ) -> dict[str, Any]:
        return {
            "contents": contents,
            "generationConfig": {"maxOutputTokens": max_tokens},
        }

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_response(self, raw: dict[str, Any]) -> tuple[str, int, int]:
        """Extract (content, input_tokens, output_tokens) from a Gemini response."""
        content = ""
        candidates = raw.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            content = "".join(p.get("text", "") for p in parts)

        usage = raw.get("usageMetadata", {})
        input_tokens = usage.get("promptTokenCount", 0)
        output_tokens = usage.get("candidatesTokenCount", 0)

        return content, input_tokens, output_tokens

    def _stop_reason(self, raw: dict[str, Any]) -> str:
        candidates = raw.get("candidates", [])
        if candidates:
            return candidates[0].get("finishReason", "STOP").lower()
        return "stop"

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _post(self, model: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        url = _BASE_URL.format(model=model)
        params = {"key": self._api_key}
        resp = await self._client.post(url, json=payload, params=params)
        resp.raise_for_status()
        return resp.json()  # type: ignore[return-value]

    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Return estimated cost in USD for the given token counts."""
        pricing = self.MODELS.get(model) or self.MODELS[self.DEFAULT_MODEL]
        return (
            input_tokens * pricing["input"] / 1_000_000
            + output_tokens * pricing["output"] / 1_000_000
        )
=======
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
>>>>>>> b0c71f2 (feat(multi-provider+h24): OpenAI/Gemini providers, H24 worker pool, watchdog, health alerter, live integrations)

    async def health_check(self) -> ProviderStatus:
        if not self._api_key:
            return ProviderStatus.UNAVAILABLE
        return self._status

<<<<<<< HEAD
    @property
    def available(self) -> bool:
        """True if an API key is configured."""
        return bool(self._api_key)
=======
    @staticmethod
    def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
        return _cost(model, input_tokens, output_tokens)
>>>>>>> b0c71f2 (feat(multi-provider+h24): OpenAI/Gemini providers, H24 worker pool, watchdog, health alerter, live integrations)
