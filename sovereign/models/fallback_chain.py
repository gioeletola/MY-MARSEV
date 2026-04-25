"""Fallback chain — tries providers in order, switches on error or unavailability."""
from __future__ import annotations

import logging
from typing import AsyncIterator

from sovereign.models.base_provider import (
    BaseProvider,
    CompletionRequest,
    CompletionResponse,
    ProviderStatus,
)

logger = logging.getLogger(__name__)


class FallbackChain:
    """
    Ordered list of providers. On each call, tries the primary; if it fails or
    is UNAVAILABLE, falls through to the next provider automatically.

    Default order: Anthropic → OpenAI → Local
    """

    def __init__(self, providers: list[BaseProvider]) -> None:
        if not providers:
            raise ValueError("FallbackChain requires at least one provider")
        self._providers = providers

    def add(self, provider: BaseProvider) -> None:
        self._providers.append(provider)

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        last_exc: Exception | None = None
        for provider in self._providers:
            status = await provider.health_check()
            if status == ProviderStatus.UNAVAILABLE:
                logger.debug("Skipping unavailable provider %s", provider.provider_id)
                continue
            try:
                logger.debug("Trying provider %s", provider.provider_id)
                response = await provider.complete(request)
                return response
            except Exception as exc:
                logger.warning("Provider %s failed: %s — falling back", provider.provider_id, exc)
                last_exc = exc

        raise RuntimeError(
            f"All providers in FallbackChain exhausted. Last error: {last_exc}"
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        last_exc: Exception | None = None
        for provider in self._providers:
            status = await provider.health_check()
            if status == ProviderStatus.UNAVAILABLE:
                continue
            try:
                async for token in provider.stream(request):
                    yield token
                return
            except Exception as exc:
                logger.warning("Provider %s stream failed: %s — falling back", provider.provider_id, exc)
                last_exc = exc

        raise RuntimeError(f"All providers in FallbackChain exhausted. Last error: {last_exc}")

    @property
    def primary(self) -> BaseProvider:
        return self._providers[0]

    def status_report(self) -> list[dict]:
        return [{"provider": p.provider_id, "status": p._status.value} for p in self._providers]
