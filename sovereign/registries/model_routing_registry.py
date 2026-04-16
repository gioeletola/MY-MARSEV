"""
Model Routing Registry — stores and evaluates model selection rules.

Provides a queryable, configurable registry for model routing decisions.
Complements the ModelRouter (which contains hard-coded heuristics) by
allowing runtime-configurable routing rules.
"""
from __future__ import annotations
import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Canonical model IDs
OPUS   = "claude-opus-4-6"
SONNET = "claude-sonnet-4-6"
HAIKU  = "claude-haiku-4-5-20251001"


@dataclass
class RoutingRule:
    """A single model routing rule."""
    rule_id: str
    name: str
    description: str
    # Match conditions (all must match if specified)
    agent_ids: list[str] = field(default_factory=list)        # specific agents
    task_keywords: list[str] = field(default_factory=list)    # objective keywords
    operating_modes: list[str] = field(default_factory=list)  # modes
    min_complexity: float = 0.0    # 0.0-1.0
    max_complexity: float = 1.0
    action_classes: list[str] = field(default_factory=list)
    # Decision
    model: str = SONNET
    reason: str = ""
    # Metadata
    enabled: bool = True
    priority: int = 50  # lower = higher priority


@dataclass
class RoutingDecision:
    """Result of routing rule evaluation."""
    model: str
    rule_id: str | None
    rule_name: str | None
    reason: str
    fallback: bool = False


class ModelRoutingRegistry:
    """
    Runtime-configurable model routing registry.

    Evaluates rules in priority order, returns first match.
    Falls back to SONNET if no rule matches.
    """

    DEFAULT_MODEL = SONNET

    def __init__(self) -> None:
        self._rules: dict[str, RoutingRule] = {}
        self._agent_overrides: dict[str, str] = {}  # agent_id → model override
        self._seed_defaults()

    # ------------------------------------------------------------------

    def register(self, rule: RoutingRule) -> None:
        self._rules[rule.rule_id] = rule
        logger.info("ModelRoutingRegistry: registered rule '%s' → %s", rule.name, rule.model)

    def set_agent_override(self, agent_id: str, model: str) -> None:
        """Pin a specific agent to a specific model, bypassing all rules."""
        self._agent_overrides[agent_id] = model
        logger.info("ModelRoutingRegistry: agent %s pinned to %s", agent_id, model)

    def clear_agent_override(self, agent_id: str) -> None:
        self._agent_overrides.pop(agent_id, None)

    def resolve(
        self,
        agent_id: str = "",
        objective: str = "",
        operating_mode: str = "",
        action_class: str = "",
        complexity: float = 0.5,
        context: dict[str, Any] | None = None,
    ) -> RoutingDecision:
        """
        Resolve the best model for a given context.
        Returns a RoutingDecision with model, rule, and reason.
        """
        # 1. Check agent-level override
        if agent_id in self._agent_overrides:
            model = self._agent_overrides[agent_id]
            return RoutingDecision(model=model, rule_id="override",
                                   rule_name="Agent override",
                                   reason=f"Agent {agent_id} pinned to {model}")

        obj_lower = objective.lower()
        sorted_rules = sorted(
            [r for r in self._rules.values() if r.enabled],
            key=lambda r: r.priority,
        )

        for rule in sorted_rules:
            # Agent check
            if rule.agent_ids and agent_id not in rule.agent_ids:
                continue
            # Mode check
            if rule.operating_modes and operating_mode not in rule.operating_modes:
                continue
            # Action class check
            if rule.action_classes and action_class not in rule.action_classes:
                continue
            # Complexity check
            if not (rule.min_complexity <= complexity <= rule.max_complexity):
                continue
            # Keyword check
            if rule.task_keywords and not any(kw.lower() in obj_lower for kw in rule.task_keywords):
                continue

            return RoutingDecision(
                model=rule.model,
                rule_id=rule.rule_id,
                rule_name=rule.name,
                reason=rule.reason or f"Rule '{rule.name}' matched",
            )

        return RoutingDecision(
            model=self.DEFAULT_MODEL,
            rule_id=None, rule_name=None,
            reason="No rule matched — using default (Sonnet)",
            fallback=True,
        )

    def list_rules(self) -> list[RoutingRule]:
        return sorted(self._rules.values(), key=lambda r: r.priority)

    def summary(self) -> dict[str, Any]:
        return {
            "total_rules": len(self._rules),
            "agent_overrides": dict(self._agent_overrides),
            "rules": [{"id": r.rule_id, "name": r.name, "model": r.model, "priority": r.priority}
                      for r in self.list_rules()],
        }

    # ------------------------------------------------------------------

    def _seed_defaults(self) -> None:
        defaults = [
            RoutingRule(rule_id="ceo_opus", name="CEO → Opus",
                        agent_ids=["ceo"], model=OPUS, priority=1,
                        reason="CEO requires highest capability model"),
            RoutingRule(rule_id="guardian_opus", name="Guardian → Opus",
                        agent_ids=["guardian"], model=OPUS, priority=1,
                        reason="Guardian safety review requires highest capability"),
            RoutingRule(rule_id="war_room_opus", name="War Room → Opus",
                        agent_ids=["war_room", "blind_spot", "second_opinion", "devils_advocate"],
                        model=OPUS, priority=2, reason="Strategic depth requires Opus"),
            RoutingRule(rule_id="financial_sonnet", name="Finance → Sonnet",
                        operating_modes=["finance"], model=SONNET, priority=10,
                        reason="Finance mode: Sonnet for cost-quality balance"),
            RoutingRule(rule_id="offline_haiku", name="Offline → Haiku",
                        operating_modes=["local_offline", "survival"],
                        model=HAIKU, priority=5, reason="Offline mode: minimize model cost"),
            RoutingRule(rule_id="high_complexity_opus", name="High complexity → Opus",
                        min_complexity=0.85, model=OPUS, priority=20,
                        reason="High complexity tasks route to Opus"),
            RoutingRule(rule_id="low_complexity_haiku", name="Low complexity → Haiku",
                        max_complexity=0.25, model=HAIKU, priority=20,
                        reason="Low complexity tasks route to Haiku for cost savings"),
            RoutingRule(rule_id="execute_sonnet", name="EXECUTE → Sonnet minimum",
                        action_classes=["EXECUTE"], model=SONNET, priority=30,
                        reason="Execution actions require at least Sonnet capability"),
        ]
        for rule in defaults:
            self._rules[rule.rule_id] = rule
