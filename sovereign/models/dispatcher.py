"""
Multi-provider dispatcher — routes CompletionRequests to the right provider.

Architecture:
  ModelRouter.route_with_fallback() → (provider, model, chain)
  ProviderDispatcher.complete(provider, model, request) → CompletionResponse

Providers:
  anthropic  → AnthropicProvider  (native SDK, prompt caching)
  openai     → OpenAIProvider     (requires OPENAI_API_KEY)
  gemini     → GeminiProvider     (requires GEMINI_API_KEY)
  perplexity → PerplexityProvider (requires PERPLEXITY_API_KEY)
  kimi       → KimiProvider       (requires MOONSHOT_API_KEY)
  qwen       → QwenProvider       (requires local Ollama)
  local      → LocalProvider      (requires local Ollama)

All providers degrade gracefully: if the key/endpoint is missing they
return a stub response (never crash the orchestrator).
"""
from __future__ import annotations

import logging
from typing import AsyncIterator

from sovereign.models.anthropic_provider import AnthropicProvider
from sovereign.models.base_provider import (
    BaseProvider,
    CompletionRequest,
    CompletionResponse,
    ProviderStatus,
)
from sovereign.models.gemini_provider import GeminiProvider
from sovereign.models.kimi_provider import KimiProvider
from sovereign.models.local_provider import LocalProvider
from sovereign.models.openai_provider import OpenAIProvider
from sovereign.models.perplexity_provider import PerplexityProvider
from sovereign.models.qwen_provider import QwenProvider

logger = logging.getLogger(__name__)


class ProviderDispatcher:
    """
    Unified execution layer for all model providers.

    Instantiates providers lazily on first use. Thread-safe for concurrent
    async calls since each provider uses its own httpx.AsyncClient per request.
    """

    def __init__(self) -> None:
        self._providers: dict[str, BaseProvider] = {}

    def _get(self, provider_id: str) -> BaseProvider:
        if provider_id not in self._providers:
            self._providers[provider_id] = self._build(provider_id)
        return self._providers[provider_id]

    @staticmethod
    def _build(provider_id: str) -> BaseProvider:
        match provider_id:
            case "anthropic":
                return AnthropicProvider()
            case "openai":
                return OpenAIProvider()
            case "gemini":
                return GeminiProvider()
            case "perplexity":
                return PerplexityProvider()
            case "kimi":
                return KimiProvider()
            case "qwen":
                return QwenProvider()
            case "local":
                return LocalProvider()
            case _:
                logger.warning("Unknown provider '%s' — falling back to local stub", provider_id)
                return LocalProvider()

    async def complete(
        self,
        provider_id: str,
        model: str,
        request: CompletionRequest,
    ) -> CompletionResponse:
        """Route a completion request to the named provider."""
        provider = self._get(provider_id)
        request.model = model
        try:
            return await provider.complete(request)
        except Exception as exc:
            provider.record_error()
            logger.error("Dispatcher: %s/%s failed: %s", provider_id, model, exc)
            return CompletionResponse(
                content=f"[{provider_id} error: {exc}]",
                model=model,
                provider=provider_id,
            )

    async def stream(
        self,
        provider_id: str,
        model: str,
        request: CompletionRequest,
    ) -> AsyncIterator[str]:
        """Stream tokens from the named provider."""
        provider = self._get(provider_id)
        request.model = model
        try:
            async for token in provider.stream(request):
                yield token
            provider.record_success()
        except Exception as exc:
            provider.record_error()
            logger.error("Dispatcher: stream %s/%s failed: %s", provider_id, model, exc)
            yield f"[{provider_id} stream error: {exc}]"

    async def health_check(self, provider_id: str) -> ProviderStatus:
        return await self._get(provider_id).health_check()

    def health_report(self) -> dict[str, str]:
        """Return status string for all instantiated providers."""
        return {
            pid: p._status.value
            for pid, p in self._providers.items()
        }


# Module-level singleton (instantiated once at orchestrator boot)
_dispatcher: ProviderDispatcher | None = None


def get_dispatcher() -> ProviderDispatcher:
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = ProviderDispatcher()
    return _dispatcher
