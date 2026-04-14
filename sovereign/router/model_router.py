"""
Model router — selects the appropriate Claude model tier for each task.

Routing decision is based on task complexity, sensitivity, latency budget,
cost constraints, and the required action class.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ModelTier(str, Enum):
    FRONTIER = "frontier"   # claude-opus-4-6 — strategic, complex, sensitive
    BALANCED = "balanced"   # claude-sonnet-4-6 — general purpose
    FAST = "fast"           # claude-haiku-4-5-20251001 — ephemeral, bulk, cheap


MODEL_IDS: dict[ModelTier, str] = {
    ModelTier.FRONTIER: "claude-opus-4-6",
    ModelTier.BALANCED: "claude-sonnet-4-6",
    ModelTier.FAST:     "claude-haiku-4-5-20251001",
}


@dataclass
class RoutingCriteria:
    """
    All inputs considered when selecting a model tier.

    task_complexity:     0.0 (trivial) → 1.0 (highly complex)
    is_sensitive:        True for PII, financial, legal, or strategic content
    latency_budget_ms:   Maximum tolerable latency (0 = no constraint)
    cost_budget_tokens:  Maximum token budget (0 = no constraint)
    action_class:        The ActionClass requested for this task
    requires_reasoning:  True if deep chain-of-thought reasoning is needed
    """

    task_complexity: float = 0.5
    is_sensitive: bool = False
    latency_budget_ms: int = 0
    cost_budget_tokens: int = 0
    action_class: str = "SUGGEST"
    requires_reasoning: bool = False


class ModelRouter:
    """
    Routes tasks to the appropriate Claude model tier.

    Rules (evaluated in priority order):
    1. Sensitive + complex → FRONTIER
    2. Requires deep reasoning → FRONTIER
    3. Complexity > 0.8 → FRONTIER
    4. Tight latency budget (< 2000ms) → FAST
    5. Low complexity (< 0.3) → FAST
    6. Default → BALANCED
    """

    def route(self, criteria: RoutingCriteria) -> str:
        """Return the model ID string for the given routing criteria."""
        tier = self._select_tier(criteria)
        return MODEL_IDS[tier]

    def route_tier(self, criteria: RoutingCriteria) -> ModelTier:
        """Return the ModelTier enum (useful for logging and config)."""
        return self._select_tier(criteria)

    def _select_tier(self, c: RoutingCriteria) -> ModelTier:
        # Hard escalation to frontier
        if c.is_sensitive and c.task_complexity > 0.5:
            return ModelTier.FRONTIER
        if c.requires_reasoning:
            return ModelTier.FRONTIER
        if c.task_complexity > 0.8:
            return ModelTier.FRONTIER

        # Fast path for latency-sensitive or trivial tasks
        if c.latency_budget_ms > 0 and c.latency_budget_ms < 2000:
            return ModelTier.FAST
        if c.task_complexity < 0.3 and not c.is_sensitive:
            return ModelTier.FAST

        return ModelTier.BALANCED

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
