"""Suggestion engine — proactively surfaces relevant actions based on context."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Any

logger = logging.getLogger(__name__)


@dataclass
class Suggestion:
    suggestion_id: str
    title: str
    description: str
    action: str
    priority: float = 0.5
    source: str = "system"
    expires_at: float = 0.0
    metadata: dict = field(default_factory=dict)
    dismissed: bool = False

    @property
    def expired(self) -> bool:
        return self.expires_at > 0 and time.time() > self.expires_at


SuggestionRule = Callable[[dict[str, Any]], list[Suggestion]]


class SuggestionEngine:
    """
    Evaluates registered rules against the current memory snapshot and
    returns a ranked list of suggestions for the user.
    """

    def __init__(self) -> None:
        self._rules: list[tuple[str, SuggestionRule]] = []
        self._active: list[Suggestion] = []
        self._dismissed: set[str] = set()
        self._register_defaults()

    def register_rule(self, rule_id: str, rule: SuggestionRule) -> None:
        self._rules.append((rule_id, rule))

    def evaluate(self, memory_snapshot: dict[str, Any]) -> list[Suggestion]:
        new_suggestions: list[Suggestion] = []
        for rule_id, rule in self._rules:
            try:
                results = rule(memory_snapshot)
                new_suggestions.extend(results)
            except Exception as exc:
                logger.warning("Suggestion rule %s failed: %s", rule_id, exc)

        self._active = [
            s for s in new_suggestions
            if s.suggestion_id not in self._dismissed and not s.expired
        ]
        self._active.sort(key=lambda s: s.priority, reverse=True)
        return self._active

    def dismiss(self, suggestion_id: str) -> None:
        self._dismissed.add(suggestion_id)
        self._active = [s for s in self._active if s.suggestion_id != suggestion_id]

    def top(self, n: int = 5) -> list[Suggestion]:
        return self._active[:n]

    def _register_defaults(self) -> None:
        self.register_rule("low_cashflow_alert", self._low_cashflow_rule)
        self.register_rule("stale_memory_reminder", self._stale_memory_rule)

    def _low_cashflow_rule(self, snap: dict) -> list[Suggestion]:
        financial = snap.get("financial", {})
        cashflow = financial.get("monthly_cashflow", None)
        if cashflow is not None and cashflow < 500:
            return [Suggestion(
                suggestion_id="low_cashflow",
                title="Low cashflow detected",
                description=f"Monthly cashflow is ${cashflow}. Consider reviewing expenses.",
                action="run cashflow_analyst",
                priority=0.9,
                source="low_cashflow_alert",
            )]
        return []

    def _stale_memory_rule(self, snap: dict) -> list[Suggestion]:
        suggestions = []
        for domain, data in snap.items():
            if isinstance(data, dict) and not data:
                suggestions.append(Suggestion(
                    suggestion_id=f"empty_{domain}_memory",
                    title=f"Empty {domain} memory",
                    description=f"The {domain} memory domain has no data. Consider populating it.",
                    action=f"populate {domain}",
                    priority=0.3,
                    source="stale_memory_reminder",
                ))
        return suggestions
