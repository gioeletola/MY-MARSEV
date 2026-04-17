"""Abstract base class for all model providers."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator


class ProviderStatus(str, Enum):
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass
class CompletionRequest:
    messages: list[dict[str, Any]]
    system: str = ""
    model: str = ""
    max_tokens: int = 4096
    temperature: float = 0.7
    tools: list[dict[str, Any]] = field(default_factory=list)
    stream: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompletionResponse:
    content: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    latency_ms: float = 0.0
    stop_reason: str = "end_turn"
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    raw: Any = None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class BaseProvider(ABC):
    provider_id: str = "base"
    display_name: str = "Base Provider"

    def __init__(self) -> None:
        self._status = ProviderStatus.AVAILABLE
        self._error_count = 0
        self._last_error_at: float = 0.0

    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Execute a completion and return a normalised response."""

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        """Stream tokens. Default: single-shot then yield."""
        resp = await self.complete(request)
        yield resp.content

    async def health_check(self) -> ProviderStatus:
        return self._status

    def record_error(self) -> None:
        self._error_count += 1
        self._last_error_at = time.time()
        if self._error_count >= 3:
            self._status = ProviderStatus.DEGRADED

    def record_success(self) -> None:
        self._error_count = 0
        self._status = ProviderStatus.AVAILABLE
