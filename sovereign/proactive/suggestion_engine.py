"""Suggestion engine — proactively surfaces relevant actions based on context."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable

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

    # ------------------------------------------------------------------
    # Rule registration
    # ------------------------------------------------------------------

    def _register_defaults(self) -> None:
        self.register_rule("low_cashflow_alert",     self._low_cashflow_rule)
        self.register_rule("overdue_actions",        self._overdue_actions_rule)
        self.register_rule("project_deadline",       self._project_deadline_rule)
        self.register_rule("open_decisions",         self._open_decisions_rule)
        self.register_rule("budget_overspend",       self._budget_overspend_rule)
        self.register_rule("stale_memory_reminder",  self._stale_memory_rule)

    # ------------------------------------------------------------------
    # Default rules
    # ------------------------------------------------------------------

    def _low_cashflow_rule(self, snap: dict) -> list[Suggestion]:
        financial = snap.get("financial", {})
        if isinstance(financial, list):
            # financial domain stores a list of entries; look for cashflow key
            cashflow = None
            for entry in financial:
                if isinstance(entry, dict) and "monthly_cashflow" in entry:
                    cashflow = entry["monthly_cashflow"]
                    break
        else:
            cashflow = financial.get("monthly_cashflow")

        if cashflow is not None and cashflow < 500:
            return [Suggestion(
                suggestion_id="low_cashflow",
                title="Low cashflow detected",
                description=f"Monthly cashflow is ${cashflow:,.0f}. Review expenses now.",
                action="run cashflow_analyst",
                priority=0.9,
                source="low_cashflow_alert",
                metadata={"cashflow": cashflow},
            )]
        return []

    def _overdue_actions_rule(self, snap: dict) -> list[Suggestion]:
        next_action = snap.get("next_action", {})
        items: list[dict] = []
        if isinstance(next_action, list):
            items = next_action
        elif isinstance(next_action, dict):
            items = list(next_action.values())

        today = date.today().isoformat()
        overdue = [
            a for a in items
            if isinstance(a, dict)
            and a.get("due_date", "") < today
            and not a.get("done", False)
            and not a.get("completed", False)
        ]
        if overdue:
            titles = ", ".join(a.get("title", "?") for a in overdue[:3])
            return [Suggestion(
                suggestion_id="overdue_actions",
                title=f"{len(overdue)} overdue action{'s' if len(overdue) > 1 else ''}",
                description=f"Overdue: {titles}{'…' if len(overdue) > 3 else ''}",
                action="python main.py run 'review my overdue tasks'",
                priority=0.85,
                source="overdue_actions",
                metadata={"count": len(overdue)},
            )]
        return []

    def _project_deadline_rule(self, snap: dict) -> list[Suggestion]:
        projects = snap.get("projects", snap.get("project", {}))
        items: list[dict] = []
        if isinstance(projects, list):
            items = projects
        elif isinstance(projects, dict):
            items = list(projects.values())

        today = date.today().isoformat()
        # warn if deadline within 14 days
        from datetime import timedelta
        warn_cutoff = (date.today() + timedelta(days=14)).isoformat()
        approaching = [
            p for p in items
            if isinstance(p, dict)
            and p.get("deadline", "")
            and today <= p.get("deadline", "") <= warn_cutoff
            and p.get("status", "") not in ("done", "completed", "cancelled")
        ]
        suggestions = []
        for p in approaching[:2]:
            suggestions.append(Suggestion(
                suggestion_id=f"deadline_{p.get('project_id', p.get('name', ''))}",
                title=f"Deadline approaching: {p.get('name', 'Project')}",
                description=f"Due {p.get('deadline')} — progress {p.get('progress', p.get('progress_pct', '?'))}%",
                action=f"run project_manager on {p.get('name', 'project')}",
                priority=0.75,
                source="project_deadline",
                metadata={"project_id": p.get("project_id"), "deadline": p.get("deadline")},
            ))
        return suggestions

    def _open_decisions_rule(self, snap: dict) -> list[Suggestion]:
        decision = snap.get("decision", {})
        items: list[dict] = []
        if isinstance(decision, list):
            items = decision
        elif isinstance(decision, dict):
            items = [decision] if decision else []

        open_dec = [
            d for d in items
            if isinstance(d, dict) and d.get("status", "open") == "open"
        ]
        if len(open_dec) >= 2:
            return [Suggestion(
                suggestion_id="open_decisions",
                title=f"{len(open_dec)} open decisions pending",
                description="Use the decision brief to resolve and record outcomes.",
                action="python main.py run 'help me close my open decisions'",
                priority=0.6,
                source="open_decisions",
                metadata={"count": len(open_dec)},
            )]
        return []

    def _budget_overspend_rule(self, snap: dict) -> list[Suggestion]:
        financial = snap.get("financial", {})
        entries: list[dict] = financial if isinstance(financial, list) else []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            budget = entry.get("monthly_budget")
            spent = entry.get("monthly_spent")
            if budget and spent and spent > budget * 0.9:
                pct = int(spent / budget * 100)
                return [Suggestion(
                    suggestion_id="budget_overspend",
                    title=f"Budget at {pct}% — review spending",
                    description=f"Spent ${spent:,.0f} of ${budget:,.0f} monthly budget.",
                    action="run expense_tracker",
                    priority=0.8,
                    source="budget_overspend",
                    metadata={"spent": spent, "budget": budget, "pct": pct},
                )]
        return []

    def _stale_memory_rule(self, snap: dict) -> list[Suggestion]:
        suggestions = []
        for domain, data in snap.items():
            if domain == "conversation_history":
                continue
            if isinstance(data, dict) and not data:
                suggestions.append(Suggestion(
                    suggestion_id=f"empty_{domain}_memory",
                    title=f"Empty {domain} memory",
                    description=f"The {domain} domain has no data. Populate it for better context.",
                    action=f"populate {domain}",
                    priority=0.25,
                    source="stale_memory_reminder",
                ))
        return suggestions
