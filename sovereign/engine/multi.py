"""
Multi-engine router — picks the best available engine for a given model_id.
Falls back through a priority chain if the preferred engine is unavailable.
"""
from __future__ import annotations

import logging
from typing import Any, AsyncIterator

from sovereign.engine.base import (
    BaseEngine, CompletionRequest, CompletionResponse, EngineHealth, EngineStatus,
)

logger = logging.getLogger(__name__)


class MultiEngine(BaseEngine):
    engine_id = "multi"
    engine_name = "Multi-Engine Router"
    supports_streaming = True
    supports_tool_use = True

    def __init__(self, engines: list[BaseEngine], config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._engines = engines

    def supports_model(self, model_id: str) -> bool:
        return any(e.supports_model(model_id) for e in self._engines)

    def _resolve(self, model_id: str) -> BaseEngine | None:
        for engine in self._engines:
            if engine.supports_model(model_id):
                return engine
        return None

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        engine = self._resolve(request.model_id)
        if engine is None:
            # Try first engine as catch-all
            if self._engines:
                engine = self._engines[0]
                logger.warning(
                    "MultiEngine: no engine supports %s, falling back to %s",
                    request.model_id, engine.engine_id,
                )
            else:
                return CompletionResponse(
                    model_id=request.model_id,
                    content="[MultiEngine: no engines registered]",
                    finish_reason="error",
                )
        return await engine.complete(request)

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        engine = self._resolve(request.model_id)
        if engine is None and self._engines:
            engine = self._engines[0]
        if engine is None:
            yield "[MultiEngine: no engines registered]"
            return
        async for chunk in engine.stream(request):
            yield chunk

    async def health(self) -> EngineHealth:
        statuses: list[EngineHealth] = []
        for engine in self._engines:
            h = await engine.health()
            statuses.append(h)

        available = [h for h in statuses if h.status == EngineStatus.AVAILABLE]
        overall = EngineStatus.AVAILABLE if available else EngineStatus.UNAVAILABLE
        all_models = [m for h in statuses for m in h.available_models]

        return EngineHealth(
            engine_id=self.engine_id,
            status=overall,
            available_models=all_models,
            latency_ms=min((h.latency_ms for h in statuses if h.latency_ms > 0), default=0.0),
        )

    def add_engine(self, engine: BaseEngine) -> None:
        self._engines.append(engine)

    def engines(self) -> list[BaseEngine]:
        return list(self._engines)
