"""
Qwen local engine adapter — Qwen models served via Ollama.
Provides model-specific presets (context window, recommended parameters).
"""
from __future__ import annotations

from sovereign.engine.base import CompletionRequest, CompletionResponse, EngineHealth
from sovereign.engine.ollama import OllamaEngine

_QWEN_MODELS = {
    "qwen3:32b": {"context": 32768, "temperature": 0.7},
    "qwen2.5:14b": {"context": 32768, "temperature": 0.7},
    "qwen2.5:7b": {"context": 32768, "temperature": 0.7},
    "qwen2.5-coder:14b": {"context": 32768, "temperature": 0.2},
    "qwen2.5-coder:7b": {"context": 32768, "temperature": 0.2},
    "qwen2.5:3b": {"context": 32768, "temperature": 0.7},
}


class QwenLocalEngine(OllamaEngine):
    """Qwen-specific Ollama adapter with sane defaults per model size."""
    engine_id = "qwen_local"
    engine_name = "Qwen Local (Ollama)"
    is_local = True

    def supports_model(self, model_id: str) -> bool:
        return model_id in _QWEN_MODELS or model_id.startswith("qwen")

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        # Apply Qwen-specific defaults
        preset = _QWEN_MODELS.get(request.model_id, {})
        if preset and request.temperature == 0.7:
            # Use coder temperature for coder models
            request = CompletionRequest(
                model_id=request.model_id,
                messages=request.messages,
                system=request.system,
                max_tokens=request.max_tokens,
                temperature=preset.get("temperature", request.temperature),
                tools=request.tools,
                extra=request.extra,
            )
        return await super().complete(request)

    async def health(self) -> EngineHealth:
        health = await super().health()
        # Filter to only Qwen models
        health.available_models = [
            m for m in health.available_models
            if m.startswith("qwen") or "qwen" in m.lower()
        ]
        return health
