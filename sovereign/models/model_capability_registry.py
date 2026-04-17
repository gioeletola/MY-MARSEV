"""Registry of model capabilities — context windows, tool support, cost per token."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ModelCapability:
    model_id: str
    provider: str
    context_window: int
    max_output_tokens: int
    supports_tools: bool = True
    supports_vision: bool = False
    supports_caching: bool = False
    input_cost_per_1k: float = 0.0   # USD
    output_cost_per_1k: float = 0.0
    speed_tier: str = "medium"        # fast / medium / slow
    privacy_safe: bool = False        # True only for local models
    notes: str = ""


_BUILTIN: list[ModelCapability] = [
    # ── Anthropic ──────────────────────────────────────────────────────────
    ModelCapability("claude-opus-4-7", "anthropic", 200_000, 32_000, True, True, True, 15.0, 75.0, "slow"),
    ModelCapability("claude-sonnet-4-6", "anthropic", 200_000, 16_000, True, True, True, 3.0, 15.0, "medium"),
    ModelCapability("claude-haiku-4-5-20251001", "anthropic", 200_000, 8_000, True, True, True, 0.25, 1.25, "fast"),
    # ── OpenAI ────────────────────────────────────────────────────────────
    ModelCapability("gpt-4o", "openai", 128_000, 16_000, True, True, False, 5.0, 15.0, "medium"),
    ModelCapability("gpt-4o-mini", "openai", 128_000, 16_000, True, True, False, 0.15, 0.60, "fast"),
    # ── Local (Ollama) ────────────────────────────────────────────────────
    ModelCapability("llama3", "local", 8_192, 4_096, False, False, False, 0.0, 0.0, "medium", True, "Ollama"),
    ModelCapability("mistral", "local", 32_768, 8_192, False, False, False, 0.0, 0.0, "fast", True, "Ollama"),
    ModelCapability("phi3", "local", 4_096, 2_048, False, False, False, 0.0, 0.0, "fast", True, "Ollama"),
]


class ModelCapabilityRegistry:
    def __init__(self) -> None:
        self._registry: dict[str, ModelCapability] = {m.model_id: m for m in _BUILTIN}

    def register(self, cap: ModelCapability) -> None:
        self._registry[cap.model_id] = cap

    def get(self, model_id: str) -> ModelCapability | None:
        return self._registry.get(model_id)

    def list_all(self) -> list[ModelCapability]:
        return list(self._registry.values())

    def by_provider(self, provider: str) -> list[ModelCapability]:
        return [m for m in self._registry.values() if m.provider == provider]

    def privacy_safe_models(self) -> list[ModelCapability]:
        return [m for m in self._registry.values() if m.privacy_safe]

    def cheapest_for_context(self, min_context: int) -> ModelCapability | None:
        candidates = [m for m in self._registry.values() if m.context_window >= min_context]
        if not candidates:
            return None
        return min(candidates, key=lambda m: m.input_cost_per_1k)

    def fastest_available(self, provider: str | None = None) -> ModelCapability | None:
        pool = self._registry.values() if provider is None else self.by_provider(provider)
        fast = [m for m in pool if m.speed_tier == "fast"]
        return fast[0] if fast else None
