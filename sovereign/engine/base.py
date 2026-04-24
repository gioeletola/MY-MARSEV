"""
Abstract base for all SOVEREIGN engine adapters.

An engine adapter wraps a model backend (cloud or local) and exposes a
uniform `complete()` / `stream()` interface used by the router and agents.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator


class EngineStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class CompletionRequest:
    model_id: str
    messages: list[dict[str, Any]]
    system: str = ""
    max_tokens: int = 4096
    temperature: float = 0.7
    tools: list[dict[str, Any]] = field(default_factory=list)
    tool_choice: str | dict | None = None
    stream: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompletionResponse:
    model_id: str
    content: str
    finish_reason: str = "stop"
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    latency_ms: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class EngineHealth:
    engine_id: str
    status: EngineStatus
    available_models: list[str] = field(default_factory=list)
    latency_ms: float = 0.0
    error: str | None = None


class BaseEngine(ABC):
    """Uniform interface all engine adapters implement."""

    engine_id: str = "base"
    engine_name: str = "Base Engine"
    supports_streaming: bool = True
    supports_tool_use: bool = False
    is_local: bool = False

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config: dict[str, Any] = config or {}

    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        ...

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        # Default: complete and yield as single chunk
        resp = await self.complete(request)
        yield resp.content

    @abstractmethod
    async def health(self) -> EngineHealth:
        ...

    @abstractmethod
    def supports_model(self, model_id: str) -> bool:
        ...
