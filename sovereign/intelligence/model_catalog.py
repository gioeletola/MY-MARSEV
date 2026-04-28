"""
SOVEREIGN Model Catalog — central, inspectable registry of all supported models.

Each entry describes capability metadata used by the router for:
- privacy-aware routing
- cost-aware routing
- latency-aware routing
- offline/local mode selection
- complexity-based model selection
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ProviderType(str, Enum):
    CLOUD = "cloud"
    LOCAL = "local"
    OPENAI_COMPAT = "openai_compat"


class ModelTier(str, Enum):
    FRONTIER = "frontier"      # Most capable, highest cost
    BALANCED = "balanced"      # General purpose
    FAST = "fast"              # Low latency, lower cost
    LOCAL = "local"            # Free, private, offline


@dataclass
class ModelEntry:
    model_id: str
    provider: str
    display_name: str
    provider_type: ProviderType
    tier: ModelTier

    # Capability scores (0.0 – 1.0)
    reasoning_strength: float = 0.7
    coding_strength: float = 0.7
    creativity: float = 0.7
    instruction_following: float = 0.8

    # Privacy / cost / latency
    privacy_safe: bool = False       # True = data stays local
    cost_per_1k_input_usd: float = 0.0
    cost_per_1k_output_usd: float = 0.0
    avg_latency_ms: float = 1000.0
    context_window_tokens: int = 8192
    multimodal: bool = False
    offline_capable: bool = False
    streaming: bool = True

    # Routing hints
    recommended_for: list[str] = field(default_factory=list)
    notes: str = ""


# ---------------------------------------------------------------------------
# Model entries
# ---------------------------------------------------------------------------

_CATALOG: list[ModelEntry] = [
    # ── Anthropic ──────────────────────────────────────────────────────────
    ModelEntry(
        model_id="claude-opus-4-6",
        provider="anthropic",
        display_name="Claude Opus 4.6",
        provider_type=ProviderType.CLOUD,
        tier=ModelTier.FRONTIER,
        reasoning_strength=0.98, coding_strength=0.95, creativity=0.96,
        instruction_following=0.99,
        cost_per_1k_input_usd=0.015, cost_per_1k_output_usd=0.075,
        avg_latency_ms=3500, context_window_tokens=200_000,
        multimodal=True, streaming=True,
        recommended_for=["strategic-decisions", "complex-reasoning", "ceo-agent", "deep-research"],
        notes="Frontier flagship. Use for CEO agent, strategy, and complex multi-step tasks.",
    ),
    ModelEntry(
        model_id="claude-sonnet-4-6",
        provider="anthropic",
        display_name="Claude Sonnet 4.6",
        provider_type=ProviderType.CLOUD,
        tier=ModelTier.BALANCED,
        reasoning_strength=0.90, coding_strength=0.92, creativity=0.88,
        instruction_following=0.95,
        cost_per_1k_input_usd=0.003, cost_per_1k_output_usd=0.015,
        avg_latency_ms=1500, context_window_tokens=200_000,
        multimodal=True, streaming=True,
        recommended_for=["general", "coding", "analysis", "coordination", "default"],
        notes="Default for most tasks. Best cost/quality balance.",
    ),
    ModelEntry(
        model_id="claude-haiku-4-5-20251001",
        provider="anthropic",
        display_name="Claude Haiku 4.5",
        provider_type=ProviderType.CLOUD,
        tier=ModelTier.FAST,
        reasoning_strength=0.78, coding_strength=0.80, creativity=0.75,
        instruction_following=0.88,
        cost_per_1k_input_usd=0.00025, cost_per_1k_output_usd=0.00125,
        avg_latency_ms=400, context_window_tokens=200_000,
        multimodal=True, streaming=True,
        recommended_for=["classification", "bulk-ops", "ephemeral-agents", "fast-tasks"],
        notes="Fastest Claude model. Use for high-volume, low-complexity tasks.",
    ),

    # ── OpenAI ─────────────────────────────────────────────────────────────
    ModelEntry(
        model_id="gpt-4o",
        provider="openai",
        display_name="GPT-4o",
        provider_type=ProviderType.CLOUD,
        tier=ModelTier.FRONTIER,
        reasoning_strength=0.92, coding_strength=0.93, creativity=0.88,
        cost_per_1k_input_usd=0.005, cost_per_1k_output_usd=0.015,
        avg_latency_ms=2000, context_window_tokens=128_000,
        multimodal=True,
        recommended_for=["fallback", "multimodal"],
        notes="OpenAI flagship. Used as cloud fallback.",
    ),
    ModelEntry(
        model_id="gpt-4o-mini",
        provider="openai",
        display_name="GPT-4o Mini",
        provider_type=ProviderType.CLOUD,
        tier=ModelTier.FAST,
        reasoning_strength=0.80, coding_strength=0.82, creativity=0.75,
        cost_per_1k_input_usd=0.00015, cost_per_1k_output_usd=0.0006,
        avg_latency_ms=600, context_window_tokens=128_000,
        multimodal=True,
        recommended_for=["budget", "fast-fallback"],
        notes="Budget OpenAI option.",
    ),

    # ── Google Gemini ───────────────────────────────────────────────────────
    ModelEntry(
        model_id="gemini-1.5-pro",
        provider="gemini",
        display_name="Gemini 1.5 Pro",
        provider_type=ProviderType.CLOUD,
        tier=ModelTier.FRONTIER,
        reasoning_strength=0.89, coding_strength=0.88, creativity=0.85,
        cost_per_1k_input_usd=0.00125, cost_per_1k_output_usd=0.005,
        avg_latency_ms=2500, context_window_tokens=1_000_000,
        multimodal=True,
        recommended_for=["large-context", "gemini-fallback"],
        notes="Huge context window. Good for document analysis.",
    ),
    ModelEntry(
        model_id="gemini-1.5-flash",
        provider="gemini",
        display_name="Gemini 1.5 Flash",
        provider_type=ProviderType.CLOUD,
        tier=ModelTier.FAST,
        reasoning_strength=0.78, coding_strength=0.75, creativity=0.76,
        cost_per_1k_input_usd=0.000075, cost_per_1k_output_usd=0.0003,
        avg_latency_ms=500, context_window_tokens=1_000_000,
        recommended_for=["budget", "large-context-fast"],
    ),

    # ── Qwen Local ─────────────────────────────────────────────────────────
    ModelEntry(
        model_id="qwen3:32b",
        provider="qwen",
        display_name="Qwen3 32B",
        provider_type=ProviderType.LOCAL,
        tier=ModelTier.FRONTIER,
        reasoning_strength=0.88, coding_strength=0.87, creativity=0.82,
        privacy_safe=True, cost_per_1k_input_usd=0.0, cost_per_1k_output_usd=0.0,
        avg_latency_ms=2000, context_window_tokens=32_768,
        offline_capable=True,
        recommended_for=["privacy", "offline", "local-frontier"],
        notes="Best local model. Requires Ollama + ~20GB VRAM.",
    ),
    ModelEntry(
        model_id="qwen2.5:14b",
        provider="qwen",
        display_name="Qwen2.5 14B",
        provider_type=ProviderType.LOCAL,
        tier=ModelTier.BALANCED,
        reasoning_strength=0.80, coding_strength=0.82, creativity=0.75,
        privacy_safe=True, cost_per_1k_input_usd=0.0, cost_per_1k_output_usd=0.0,
        avg_latency_ms=1200, context_window_tokens=32_768,
        offline_capable=True,
        recommended_for=["privacy", "offline", "local-balanced", "default-local"],
        notes="Recommended local default. Requires Ollama + ~8GB VRAM.",
    ),
    ModelEntry(
        model_id="qwen2.5:7b",
        provider="qwen",
        display_name="Qwen2.5 7B",
        provider_type=ProviderType.LOCAL,
        tier=ModelTier.FAST,
        reasoning_strength=0.72, coding_strength=0.74, creativity=0.68,
        privacy_safe=True, cost_per_1k_input_usd=0.0, cost_per_1k_output_usd=0.0,
        avg_latency_ms=600, context_window_tokens=32_768,
        offline_capable=True,
        recommended_for=["privacy", "offline", "local-fast", "caveman"],
        notes="Fastest local Qwen. Requires Ollama + ~4GB VRAM.",
    ),
    ModelEntry(
        model_id="qwen2.5-coder:14b",
        provider="qwen",
        display_name="Qwen2.5 Coder 14B",
        provider_type=ProviderType.LOCAL,
        tier=ModelTier.BALANCED,
        reasoning_strength=0.78, coding_strength=0.92, creativity=0.65,
        privacy_safe=True, cost_per_1k_input_usd=0.0, cost_per_1k_output_usd=0.0,
        avg_latency_ms=1200, context_window_tokens=32_768,
        offline_capable=True,
        recommended_for=["coding", "code-review", "local-coding"],
        notes="Best local model for code tasks.",
    ),

    # ── Ollama (generic local) ──────────────────────────────────────────────
    ModelEntry(
        model_id="ollama-mistral",
        provider="local",
        display_name="Mistral 7B (Ollama)",
        provider_type=ProviderType.LOCAL,
        tier=ModelTier.LOCAL,
        reasoning_strength=0.65, coding_strength=0.68, creativity=0.65,
        privacy_safe=True, cost_per_1k_input_usd=0.0, cost_per_1k_output_usd=0.0,
        avg_latency_ms=800, context_window_tokens=8192,
        offline_capable=True,
        recommended_for=["caveman", "offline-fallback"],
        notes="Last-resort local fallback when all else fails.",
    ),
]


class ModelCatalog:
    """Queryable catalog of all supported models."""

    def __init__(self) -> None:
        self._entries: dict[str, ModelEntry] = {e.model_id: e for e in _CATALOG}

    def get(self, model_id: str) -> ModelEntry | None:
        return self._entries.get(model_id)

    def all(self) -> list[ModelEntry]:
        return list(self._entries.values())

    def by_provider(self, provider: str) -> list[ModelEntry]:
        return [e for e in self._entries.values() if e.provider == provider]

    def by_tier(self, tier: ModelTier) -> list[ModelEntry]:
        return [e for e in self._entries.values() if e.tier == tier]

    def local_models(self) -> list[ModelEntry]:
        return [e for e in self._entries.values() if e.offline_capable]

    def privacy_safe_models(self) -> list[ModelEntry]:
        return [e for e in self._entries.values() if e.privacy_safe]

    def for_use_case(self, use_case: str) -> list[ModelEntry]:
        return [e for e in self._entries.values() if use_case in e.recommended_for]

    def cheapest(self, max_input_cost: float = 999.0) -> list[ModelEntry]:
        return sorted(
            [e for e in self._entries.values() if e.cost_per_1k_input_usd <= max_input_cost],
            key=lambda e: e.cost_per_1k_input_usd,
        )

    def to_dict_list(self) -> list[dict[str, Any]]:
        return [
            {
                "model_id": e.model_id,
                "provider": e.provider,
                "display_name": e.display_name,
                "provider_type": e.provider_type.value,
                "tier": e.tier.value,
                "reasoning_strength": e.reasoning_strength,
                "coding_strength": e.coding_strength,
                "privacy_safe": e.privacy_safe,
                "cost_per_1k_input_usd": e.cost_per_1k_input_usd,
                "cost_per_1k_output_usd": e.cost_per_1k_output_usd,
                "avg_latency_ms": e.avg_latency_ms,
                "context_window_tokens": e.context_window_tokens,
                "multimodal": e.multimodal,
                "offline_capable": e.offline_capable,
                "recommended_for": e.recommended_for,
                "notes": e.notes,
            }
            for e in self._entries.values()
        ]


_catalog: ModelCatalog | None = None


def get_model_catalog() -> ModelCatalog:
    global _catalog
    if _catalog is None:
        _catalog = ModelCatalog()
    return _catalog


# ---------------------------------------------------------------------------
# ModelSelector — smart model selection from the catalog
# ---------------------------------------------------------------------------

_TASK_WEIGHTS: dict[str, dict[str, float]] = {
    "coding":     {"coding_strength": 0.6, "reasoning_strength": 0.3, "instruction_following": 0.1},
    "reasoning":  {"reasoning_strength": 0.7, "coding_strength": 0.1, "instruction_following": 0.2},
    "creative":   {"creativity": 0.6, "instruction_following": 0.3, "reasoning_strength": 0.1},
    "general":    {"reasoning_strength": 0.35, "instruction_following": 0.35, "coding_strength": 0.15, "creativity": 0.15},
    "fast":       {"instruction_following": 0.5, "reasoning_strength": 0.5},
    "multimodal": {"multimodal": 1.0},
}


class ModelSelector:
    """
    Smart model selection from the ModelCatalog.

    Usage::
        selector = ModelSelector()
        best = selector.best_for("coding")
        cheap = selector.cheapest_for("general", min_reasoning=0.7)
        private = selector.most_private()
    """

    def __init__(self, catalog: ModelCatalog | None = None) -> None:
        self._catalog = catalog or get_model_catalog()

    def _score(self, entry: "ModelEntry", task_type: str) -> float:  # type: ignore[name-defined]
        weights = _TASK_WEIGHTS.get(task_type, _TASK_WEIGHTS["general"])
        score = 0.0
        for attr, w in weights.items():
            if attr == "multimodal":
                score += w if entry.multimodal else 0.0
            else:
                score += getattr(entry, attr, 0.5) * w
        return round(score, 4)

    def best_for(self, task_type: str) -> "ModelEntry":  # type: ignore[name-defined]
        """Return the highest-scoring cloud model for *task_type*."""
        entries = [e for e in self._catalog.all() if e.provider_type.value != "local"]
        if not entries:
            return self._catalog.all()[0]
        return max(entries, key=lambda e: self._score(e, task_type))

    def cheapest_for(self, task_type: str, min_reasoning: float = 0.7) -> "ModelEntry":  # type: ignore[name-defined]
        """Cheapest model with reasoning_strength >= min_reasoning."""
        candidates = [
            e for e in self._catalog.all()
            if e.reasoning_strength >= min_reasoning
        ]
        if not candidates:
            candidates = self._catalog.all()
        return min(candidates, key=lambda e: e.cost_per_1k_input_usd + e.cost_per_1k_output_usd)

    def most_private(self) -> "list[ModelEntry]":  # type: ignore[name-defined]
        """Return all privacy-safe (local) models."""
        return [e for e in self._catalog.all() if e.privacy_safe or e.offline_capable]

    def compare(self, model_a_id: str, model_b_id: str, task_type: str = "general") -> dict:
        """Side-by-side capability comparison of two models."""
        a = self._catalog.get(model_a_id)
        b = self._catalog.get(model_b_id)
        if not a or not b:
            return {"error": "One or both models not found"}
        attrs = ["reasoning_strength", "coding_strength", "creativity",
                 "instruction_following", "cost_per_1k_input_usd", "avg_latency_ms"]
        return {
            "model_a": model_a_id,
            "model_b": model_b_id,
            "task_type": task_type,
            "score_a": self._score(a, task_type),
            "score_b": self._score(b, task_type),
            "winner": model_a_id if self._score(a, task_type) >= self._score(b, task_type) else model_b_id,
            "attributes": {
                attr: {"a": getattr(a, attr, None), "b": getattr(b, attr, None)}
                for attr in attrs
            },
        }

    def benchmark_score(self, model_id: str, task_type: str = "general") -> float:
        entry = self._catalog.get(model_id)
        if not entry:
            return 0.0
        return self._score(entry, task_type)

    def top_n(self, task_type: str, n: int = 5) -> "list[ModelEntry]":  # type: ignore[name-defined]
        entries = self._catalog.all()
        return sorted(entries, key=lambda e: self._score(e, task_type), reverse=True)[:n]

