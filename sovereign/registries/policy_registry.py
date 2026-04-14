"""Policy registry — stores named policy rules loaded from config."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PolicyRule:
    """A named policy rule with conditions and action."""
    name: str
    condition: dict[str, Any]   # Arbitrary condition descriptor
    action: str                  # "allow" | "deny" | "escalate"
    rationale: str = ""
    priority: int = 50


class PolicyRegistry:
    """Stores and evaluates named policy rules."""

    def __init__(self) -> None:
        self._rules: list[PolicyRule] = []

    def add_rule(self, rule: PolicyRule) -> None:
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def evaluate(self, context: dict[str, Any]) -> str:
        """
        Evaluate all rules against context and return the highest-priority decision.

        Returns "allow", "deny", or "escalate".
        Falls back to "allow" if no rule matches.
        """
        for rule in self._rules:
            if self._matches(rule.condition, context):
                return rule.action
        return "allow"

    @staticmethod
    def _matches(condition: dict[str, Any], context: dict[str, Any]) -> bool:
        """Simple key=value matching. Extend with a rule engine for production."""
        return all(context.get(k) == v for k, v in condition.items())

    def list_rules(self) -> list[str]:
        return [r.name for r in self._rules]
