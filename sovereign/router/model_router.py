"""
Model router — selects the appropriate model+provider for each task.

Routing considers: task complexity, sensitivity, latency budget, cost,
privacy constraints (PII), and provider health. Supports fallback chains
and an offline/caveman mode when all providers are unavailable.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pricing tables (USD per 1M tokens)
# ---------------------------------------------------------------------------

_PROVIDER_PRICING: dict[str, dict[str, tuple[float, float]]] = {
    "anthropic": {
        "claude-opus-4-7":           (15.00, 75.00),
        "claude-sonnet-4-6":         (3.00,  15.00),
        "claude-haiku-4-5-20251001":  (0.80,   4.00),
    },
    "openai": {
        "gpt-4o":      (5.00,  15.00),
        "gpt-4o-mini": (0.15,   0.60),
        "o1-mini":     (3.00,  12.00),
    },
    "gemini": {
        "gemini-1.5-flash": (0.00,  0.00),
        "gemini-1.5-pro":   (3.50, 10.50),
    },
    "perplexity": {
        "sonar":     (1.00, 1.00),
        "sonar-pro": (3.00, 15.00),
    },
    "kimi": {
        "moonshot-v1-8k":          (1.65,  1.65),
        "moonshot-v1-32k":         (3.30,  3.30),
        "moonshot-v1-128k":        (8.25,  8.25),
        "kimi-latest":             (8.25,  8.25),
        "kimi-thinking-preview":  (16.50, 16.50),
    },
    "qwen": {
        "qwen2.5:7b":        (0.00, 0.00),
        "qwen2.5:14b":       (0.00, 0.00),
        "qwen2.5:32b":       (0.00, 0.00),
        "qwen2.5:72b":       (0.00, 0.00),
        "qwen2.5-coder:7b":  (0.00, 0.00),
        "qwen2.5-coder:14b": (0.00, 0.00),
        "qwen3:8b":          (0.00, 0.00),
        "qwen3:14b":         (0.00, 0.00),
        "qwen3:32b":         (0.00, 0.00),
    },
    "local": {
        "ollama-mistral": (0.00, 0.00),
        "ollama-llama3":  (0.00, 0.00),
    },
}


class ModelTier(str, Enum):
    FRONTIER = "frontier"   # claude-opus-4-7 — strategic, complex, sensitive
    BALANCED = "balanced"   # claude-sonnet-4-6 — general purpose
    FAST = "fast"           # claude-haiku-4-5-20251001 — ephemeral, bulk, cheap


MODEL_IDS: dict[ModelTier, str] = {
    ModelTier.FRONTIER: "claude-opus-4-7",
    ModelTier.BALANCED: "claude-sonnet-4-6",
    ModelTier.FAST:     "claude-haiku-4-5-20251001",
}


@dataclass
class RoutingCriteria:
    """All inputs considered when selecting a model tier."""
    task_complexity: float = 0.5
    is_sensitive: bool = False
    latency_budget_ms: int = 0      # 0 = no constraint
    cost_budget_tokens: int = 0     # 0 = no constraint
    action_class: str = "SUGGEST"
    requires_reasoning: bool = False
    contains_pii: bool = False      # must stay on-premise if True
    preferred_provider: str = "anthropic"
    budget_limit_usd: float = 1.0


# ---------------------------------------------------------------------------
# Provider health tracking
# ---------------------------------------------------------------------------

@dataclass
class ProviderHealth:
    """Tracks real-time health of a provider."""
    provider: str
    available: bool = True
    error_count: int = 0
    last_error_at: float = 0.0
    latency_p50_ms: float = 0.0
    circuit_open: bool = False   # True = provider is blocked
    _error_window: list[float] = field(default_factory=list, repr=False)

    ERROR_THRESHOLD = 3          # errors within window to open circuit
    WINDOW_SECONDS = 60.0
    RECOVERY_SECONDS = 120.0     # how long circuit stays open

    def record_success(self, latency_ms: float = 0.0) -> None:
        self.available = True
        if latency_ms > 0:
            self.latency_p50_ms = (self.latency_p50_ms * 0.8 + latency_ms * 0.2)
        self._prune_window()

    def record_error(self) -> None:
        now = time.time()
        self._error_window.append(now)
        self._prune_window()
        self.error_count += 1
        self.last_error_at = now
        if len(self._error_window) >= self.ERROR_THRESHOLD:
            self.circuit_open = True
            self.available = False
            logger.warning("ProviderHealth: circuit OPEN for %s", self.provider)

    def check_recovery(self) -> bool:
        """Allow recovery if circuit has been open long enough."""
        if not self.circuit_open:
            return True
        elapsed = time.time() - self.last_error_at
        if elapsed >= self.RECOVERY_SECONDS:
            self.circuit_open = False
            self.available = True
            self._error_window.clear()
            logger.info("ProviderHealth: circuit CLOSED for %s (recovered)", self.provider)
            return True
        return False

    def is_healthy(self) -> bool:
        if self.circuit_open:
            return self.check_recovery()
        return self.available

    def _prune_window(self) -> None:
        cutoff = time.time() - self.WINDOW_SECONDS
        self._error_window = [t for t in self._error_window if t > cutoff]


class ProviderHealthTracker:
    """Registry of all known provider health states."""

    def __init__(self) -> None:
        self._health: dict[str, ProviderHealth] = {
            p: ProviderHealth(provider=p)
            for p in _PROVIDER_PRICING
        }

    def get(self, provider: str) -> ProviderHealth:
        if provider not in self._health:
            self._health[provider] = ProviderHealth(provider=provider)
        return self._health[provider]

    def is_healthy(self, provider: str) -> bool:
        return self.get(provider).is_healthy()

    def record_success(self, provider: str, latency_ms: float = 0.0) -> None:
        self.get(provider).record_success(latency_ms)

    def record_error(self, provider: str) -> None:
        self.get(provider).record_error()

    def healthy_providers(self) -> list[str]:
        return [p for p in self._health if self._health[p].is_healthy()]

    def report(self) -> dict[str, Any]:
        return {
            p: {
                "available": h.available,
                "circuit_open": h.circuit_open,
                "error_count": h.error_count,
                "latency_p50_ms": round(h.latency_p50_ms, 1),
            }
            for p, h in self._health.items()
        }


# ---------------------------------------------------------------------------
# Fallback chain builder
# ---------------------------------------------------------------------------

def build_fallback_chain(
    primary_provider: str,
    primary_model: str,
    contains_pii: bool = False,
    offline_only: bool = False,
) -> list[tuple[str, str]]:
    """
    Build an ordered fallback chain: primary → alternatives → local.

    PII-sensitive tasks never leave local/anthropic (on-premise options).
    offline_only restricts to local models only.
    """
    if offline_only:
        return [("local", "ollama-mistral")]

    chain: list[tuple[str, str]] = [(primary_provider, primary_model)]

    if contains_pii:
        # PII: only allow anthropic (enterprise agreement) or local
        if primary_provider != "anthropic":
            chain = [("anthropic", MODEL_IDS[ModelTier.BALANCED])]
        chain.append(("local", "ollama-mistral"))
        return chain

    # Standard fallback order
    fallbacks: list[tuple[str, str]] = [
        ("anthropic", "claude-sonnet-4-6"),
        ("openai",    "gpt-4o-mini"),
        ("gemini",    "gemini-1.5-flash"),
        ("kimi",      "moonshot-v1-32k"),
        ("qwen",      "qwen2.5:14b"),
        ("local",     "ollama-mistral"),
    ]
    for fb in fallbacks:
        if fb not in chain:
            chain.append(fb)
    return chain


# ---------------------------------------------------------------------------
# Main router
# ---------------------------------------------------------------------------

class ModelRouter:
    """
    Routes tasks to the best (provider, model) pair.

    Features:
    - Multi-provider: Anthropic, OpenAI, Gemini, Perplexity, Kimi, Qwen, local
    - Fallback chain with circuit-breaker per provider
    - Privacy gate: PII tasks stay on anthropic/local
    - Cost-aware: respects budget_limit_usd
    - Latency-aware: tight budgets → FAST tier or local
    - Offline/caveman mode: all cloud providers fail → local only
    """

    def __init__(self) -> None:
        self.health = ProviderHealthTracker()
        self._model_scores: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Primary API
    # ------------------------------------------------------------------

    def route(self, criteria: RoutingCriteria) -> str:
        """Return the Claude model ID string for the given criteria."""
        tier = self._select_tier(criteria)
        return MODEL_IDS[tier]

    def route_tier(self, criteria: RoutingCriteria) -> ModelTier:
        return self._select_tier(criteria)

    def route_with_fallback(
        self,
        criteria: RoutingCriteria,
    ) -> tuple[str, str, list[tuple[str, str]]]:
        """
        Return (provider, model, fallback_chain).

        Selects the best healthy provider/model pair using the fallback chain.
        Falls back through alternatives if the primary provider is unhealthy.
        """
        primary_provider, primary_model = self._select_provider_model(criteria)
        chain = build_fallback_chain(
            primary_provider, primary_model,
            contains_pii=criteria.contains_pii,
        )
        for provider, model in chain:
            if self.health.is_healthy(provider):
                logger.debug("Router: selected %s/%s", provider, model)
                return provider, model, chain

        # All cloud providers down → try qwen then local (caveman mode)
        if self.health.is_healthy("qwen"):
            logger.info("Router: cloud down — falling back to qwen")
            return "qwen", "qwen2.5:14b", chain
        logger.warning("Router: ALL providers down — caveman mode (local only)")
        return "local", "ollama-mistral", chain

    # ------------------------------------------------------------------
    # Provider/model selection logic
    # ------------------------------------------------------------------

    def _select_provider_model(self, criteria: RoutingCriteria) -> tuple[str, str]:
        """Choose (provider, model) before applying health/fallback."""
        c = criteria

        # Privacy constraint: PII must stay on anthropic or local
        if c.contains_pii:
            return ("anthropic", self._select_tier_model(c))

        # Budget constraint: ultra-low budget → cheapest
        if c.budget_limit_usd < 0.001:
            return ("openai", "gpt-4o-mini")

        # Latency constraint: very tight → local or haiku
        if c.latency_budget_ms > 0 and c.latency_budget_ms < 500:
            return ("local", "ollama-mistral")

        # High complexity → frontier
        if c.task_complexity >= 0.8 or c.requires_reasoning:
            return ("anthropic", MODEL_IDS[ModelTier.FRONTIER])

        # Preferred provider hint
        if c.preferred_provider == "openai":
            model = "gpt-4o" if c.task_complexity >= 0.5 else "gpt-4o-mini"
            return ("openai", model)
        if c.preferred_provider == "gemini":
            model = "gemini-1.5-pro" if c.task_complexity >= 0.5 else "gemini-1.5-flash"
            return ("gemini", model)
        if c.preferred_provider == "perplexity":
            return ("perplexity", "sonar")
        if c.preferred_provider == "kimi":
            model = "kimi-latest" if c.task_complexity >= 0.7 else "moonshot-v1-32k"
            return ("kimi", model)
        if c.preferred_provider == "qwen":
            model = "qwen3:32b" if c.task_complexity >= 0.8 else (
                "qwen2.5:14b" if c.task_complexity >= 0.5 else "qwen2.5:7b"
            )
            return ("qwen", model)
        if c.preferred_provider == "local":
            return ("local", "ollama-mistral")

        # Default: anthropic balanced/fast
        return ("anthropic", self._select_tier_model(c))

    def _select_tier_model(self, c: RoutingCriteria) -> str:
        tier = self._select_tier(c)
        return MODEL_IDS[tier]

    def _select_tier(self, c: RoutingCriteria) -> ModelTier:
        if c.is_sensitive and c.task_complexity > 0.5:
            return ModelTier.FRONTIER
        if c.requires_reasoning:
            return ModelTier.FRONTIER
        if c.task_complexity > 0.8:
            return ModelTier.FRONTIER
        if c.latency_budget_ms > 0 and c.latency_budget_ms < 2000:
            return ModelTier.FAST
        if c.task_complexity < 0.3 and not c.is_sensitive:
            return ModelTier.FAST
        return ModelTier.BALANCED

    # ------------------------------------------------------------------
    # Legacy multi-provider method (kept for compatibility)
    # ------------------------------------------------------------------

    def route_to_provider(
        self,
        task_complexity: float = 0.5,
        budget_limit_usd: float = 1.0,
        preferred_provider: str = "anthropic",
    ) -> tuple[str, str]:
        criteria = RoutingCriteria(
            task_complexity=task_complexity,
            budget_limit_usd=budget_limit_usd,
            preferred_provider=preferred_provider,
        )
        provider, model, _ = self.route_with_fallback(criteria)
        return provider, model

    # ------------------------------------------------------------------
    # Agent shortcuts
    # ------------------------------------------------------------------

    @classmethod
    def for_agent(cls, agent_id: str) -> str:
        """Return the canonical model ID for a named agent."""
        AGENT_MODELS: dict[str, str] = {
            "ceo":            MODEL_IDS[ModelTier.FRONTIER],
            "decision_brief": MODEL_IDS[ModelTier.FRONTIER],
            "research":       MODEL_IDS[ModelTier.FRONTIER],
            "guardian":       MODEL_IDS[ModelTier.BALANCED],
            "chief_of_staff": MODEL_IDS[ModelTier.BALANCED],
            "coordinator":    MODEL_IDS[ModelTier.BALANCED],
            "task_setter":    MODEL_IDS[ModelTier.BALANCED],
            "worker":         MODEL_IDS[ModelTier.BALANCED],
            "system":         MODEL_IDS[ModelTier.FAST],
        }
        return AGENT_MODELS.get(agent_id, MODEL_IDS[ModelTier.BALANCED])

    # ------------------------------------------------------------------
    # Cost estimation
    # ------------------------------------------------------------------

    @staticmethod
    def estimate_cost(
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Return estimated USD cost for the given provider/model/token counts."""
        provider_table = _PROVIDER_PRICING.get(provider, {})
        prices = provider_table.get(model)
        if not prices:
            return 0.0
        return round(
            (input_tokens / 1_000_000) * prices[0]
            + (output_tokens / 1_000_000) * prices[1],
            6,
        )

    def provider_health_report(self) -> dict[str, Any]:
        return self.health.report()

    # ------------------------------------------------------------------
    # Complexity estimation
    # ------------------------------------------------------------------

    @staticmethod
    def estimate_complexity(text: str) -> float:
        """Heuristic 0.0–1.0 complexity score for a text prompt."""
        import re as _re
        score = 0.0
        length = len(text)
        # Length signal
        score += min(length / 4000, 0.3)
        # Code blocks
        if _re.search(r"```|def |class |import |SELECT |CREATE ", text):
            score += 0.15
        # Math / reasoning
        if _re.search(r"\b(prove|derive|calculate|optimize|theorem|algorithm)\b", text, _re.I):
            score += 0.15
        # Multi-step questions
        if len(_re.findall(r"\?", text)) >= 3:
            score += 0.1
        # Nested structure
        if _re.search(r"\b(first|second|third|then|finally|however|therefore)\b", text, _re.I):
            score += 0.1
        # Technical terms
        technical = _re.findall(r"\b(API|database|architecture|infrastructure|security|compliance)\b", text, _re.I)
        score += min(len(technical) * 0.03, 0.12)
        return min(round(score, 3), 1.0)

    # ------------------------------------------------------------------
    # Batch routing
    # ------------------------------------------------------------------

    def route_parallel(self, tasks: list[str], base_criteria: RoutingCriteria | None = None) -> list[str]:
        """Return the optimal model ID for each task in a batch."""
        base = base_criteria or RoutingCriteria()
        result = []
        for task in tasks:
            c = RoutingCriteria(
                task_complexity=self.estimate_complexity(task),
                is_sensitive=base.is_sensitive,
                latency_budget_ms=base.latency_budget_ms,
                contains_pii=base.contains_pii,
                preferred_provider=base.preferred_provider,
                budget_limit_usd=base.budget_limit_usd,
            )
            result.append(self.route(c))
        return result

    # ------------------------------------------------------------------
    # Online learning — EMA score updates
    # ------------------------------------------------------------------

    def learning_rate_adjust(
        self,
        model_id: str,
        success: bool,
        latency_ms: float = 0.0,
        alpha: float = 0.15,
    ) -> float:
        """Update the model's performance score via exponential moving average."""
        current = self._model_scores.get(model_id, 0.8)
        # Combine success signal and latency penalty
        latency_penalty = min(latency_ms / 30_000, 0.3) if latency_ms > 0 else 0.0
        observed = (1.0 if success else 0.0) - latency_penalty
        updated = round(current * (1 - alpha) + observed * alpha, 4)
        self._model_scores[model_id] = updated
        return updated

    def model_score(self, model_id: str) -> float:
        return self._model_scores.get(model_id, 0.8)


@dataclass
class ModelRoutingDecision:
    """Full record of a routing decision for observability and audit."""
    model_id: str
    provider: str
    tier: str
    reason: str
    estimated_cost_usd: float = 0.0
    privacy_safe: bool = False
    fallback_chain: list[tuple[str, str]] = field(default_factory=list)
    complexity_score: float = 0.0
    latency_budget_ms: int = 0
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "provider": self.provider,
            "tier": self.tier,
            "reason": self.reason,
            "estimated_cost_usd": self.estimated_cost_usd,
            "privacy_safe": self.privacy_safe,
            "complexity_score": self.complexity_score,
        }

