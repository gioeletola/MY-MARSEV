"""
Policy registry — stores named policy rules and evaluates them against context.

Rules are priority-ordered. The first matching rule wins.
Used by GuardianAgent to gate EXECUTE-class actions.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PolicyRule:
    """A named policy rule with conditions and action."""
    name: str
    condition: dict[str, Any]   # key-value conditions (supports regex via _re_ prefix)
    action: str                  # "allow" | "deny" | "escalate"
    rationale: str = ""
    priority: int = 50           # Higher = evaluated first


class PolicyRegistry:
    """
    Stores and evaluates named policy rules.

    Condition matching supports:
      - Exact match:   {"action_class": "EXECUTE"}
      - Regex match:   {"_re_objective": "delete|drop|destroy"}
      - Range check:   {"_gte_risk_score": 0.8}
      - Membership:    {"_in_mode": ["finance", "legal"]}
    """

    def __init__(self) -> None:
        self._rules: list[PolicyRule] = []

    def add_rule(self, rule: PolicyRule) -> None:
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def evaluate(self, context: dict[str, Any]) -> tuple[str, str]:
        """
        Evaluate all rules against context.

        Returns (action, rationale) where action is "allow", "deny", or "escalate".
        Falls back to ("allow", "No matching policy rule — default allow") if no match.
        """
        for rule in self._rules:
            if self._matches(rule.condition, context):
                return rule.action, rule.rationale or f"Rule '{rule.name}' matched."
        return "allow", "No matching policy rule — default allow."

    def list_rules(self) -> list[str]:
        return [r.name for r in self._rules]

    @staticmethod
    def _matches(condition: dict[str, Any], context: dict[str, Any]) -> bool:
        """
        Extended condition matching:
          Normal key:   exact equality
          _re_<key>:    regex search on str(context[key])
          _gte_<key>:   context[key] >= value
          _lte_<key>:   context[key] <= value
          _in_<key>:    context[key] in value (value is a list)
        """
        for k, v in condition.items():
            if k.startswith("_re_"):
                field_name = k[4:]
                field_val = str(context.get(field_name, ""))
                if not re.search(str(v), field_val, re.IGNORECASE):
                    return False
            elif k.startswith("_gte_"):
                field_name = k[5:]
                field_val = context.get(field_name, 0)
                try:
                    if float(field_val) < float(v):
                        return False
                except (TypeError, ValueError):
                    return False
            elif k.startswith("_lte_"):
                field_name = k[5:]
                field_val = context.get(field_name, 0)
                try:
                    if float(field_val) > float(v):
                        return False
                except (TypeError, ValueError):
                    return False
            elif k.startswith("_in_"):
                field_name = k[4:]
                field_val = context.get(field_name)
                if field_val not in v:
                    return False
            else:
                if context.get(k) != v:
                    return False
        return True


def build_default_policy_registry() -> PolicyRegistry:
    """
    Create a PolicyRegistry pre-loaded with the SOVEREIGN AI OS default rules.

    These implement the spec's core safety + sovereignty principles.
    """
    reg = PolicyRegistry()

    # Hard deny: destructive CLI patterns
    reg.add_rule(PolicyRule(
        name="deny_destructive_cli",
        condition={"_re_objective": r"\b(rm\s+-rf|DROP TABLE|DELETE FROM|format\s+[A-Z]:)"},
        action="deny",
        rationale="Destructive irreversible operation blocked by policy.",
        priority=100,
    ))

    # Hard deny: credential / secret exfiltration
    reg.add_rule(PolicyRule(
        name="deny_secret_exfiltration",
        condition={"_re_objective": r"(api.?key|secret|password|token|credentials).*(send|upload|post|share)"},
        action="deny",
        rationale="Potential secret exfiltration detected. Blocked.",
        priority=100,
    ))

    # Escalate: high risk score
    reg.add_rule(PolicyRule(
        name="escalate_high_risk",
        condition={"_gte_risk_score": 0.75},
        action="escalate",
        rationale="Risk score exceeds threshold (0.75) — requires human approval.",
        priority=90,
    ))

    # Escalate: finance mode + EXECUTE class
    reg.add_rule(PolicyRule(
        name="escalate_finance_execute",
        condition={"action_class": "EXECUTE", "_in_mode": ["finance"]},
        action="escalate",
        rationale="Financial EXECUTE actions always require human approval.",
        priority=85,
    ))

    # Escalate: legal outputs always need review
    reg.add_rule(PolicyRule(
        name="escalate_legal_execute",
        condition={"action_class": "EXECUTE", "_in_mode": ["legal"]},
        action="escalate",
        rationale="Legal EXECUTE actions always require human approval.",
        priority=85,
    ))

    # Allow: READ / SUGGEST always pass
    reg.add_rule(PolicyRule(
        name="allow_read_suggest",
        condition={"_in_action_class": ["READ", "SUGGEST"]},
        action="allow",
        rationale="READ and SUGGEST actions are always permitted.",
        priority=10,
    ))

    return reg
