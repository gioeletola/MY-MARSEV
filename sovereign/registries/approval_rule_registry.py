"""
Approval Rule Registry — stores, evaluates, and manages approval rules.

Complements the ApprovalGate (which handles interaction) by providing
a structured, queryable rule database. Rules define: when approval is required,
who can approve, what auto-approval criteria exist, and what the timeout policy is.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ApprovalRule:
    """A single approval rule."""
    rule_id: str
    name: str
    description: str
    # Trigger conditions
    action_classes: list[str]          # ["EXECUTE"] — which action classes trigger this
    keywords: list[str] = field(default_factory=list)    # objective keywords that trigger
    agent_ids: list[str] = field(default_factory=list)   # specific agents that trigger
    min_risk_score: float = 0.0        # only trigger if risk >= this
    # Approval config
    auto_approve_below_risk: float = 0.3  # auto-approve if risk < this
    timeout_seconds: int = 3600        # seconds before timeout → default action
    timeout_default: str = "reject"    # "approve" | "reject" | "escalate"
    approvers: list[str] = field(default_factory=list)   # ["human", "guardian", "ceo"]
    # Metadata
    enabled: bool = True
    priority: int = 50                 # lower = checked first
    tags: list[str] = field(default_factory=list)


@dataclass
class RuleEvalResult:
    """Result of evaluating rules against a candidate action."""
    triggered: bool
    rule_id: str | None
    rule_name: str | None
    auto_approve: bool
    reason: str
    timeout_seconds: int = 3600
    timeout_default: str = "reject"


class ApprovalRuleRegistry:
    """
    Queryable database of approval rules.

    Rules are evaluated in priority order. First matching rule wins.
    Provides auto-approval decisions and human-escalation triggers.
    """

    def __init__(self) -> None:
        self._rules: dict[str, ApprovalRule] = {}
        self._seed_defaults()

    # ------------------------------------------------------------------

    def register(self, rule: ApprovalRule) -> None:
        self._rules[rule.rule_id] = rule
        logger.info("ApprovalRuleRegistry: registered rule '%s'", rule.name)

    def unregister(self, rule_id: str) -> bool:
        return bool(self._rules.pop(rule_id, None))

    def get(self, rule_id: str) -> ApprovalRule | None:
        return self._rules.get(rule_id)

    def evaluate(
        self,
        action_class: str,
        objective: str,
        agent_id: str,
        risk_score: float,
        context: dict[str, Any] | None = None,
    ) -> RuleEvalResult:
        """
        Evaluate all enabled rules against an action.
        Returns the first matching rule's decision, or no-trigger if none match.
        """
        obj_lower = objective.lower()
        sorted_rules = sorted(
            [r for r in self._rules.values() if r.enabled],
            key=lambda r: r.priority,
        )

        for rule in sorted_rules:
            # Check action class
            if action_class not in rule.action_classes:
                continue
            # Check risk score
            if risk_score < rule.min_risk_score:
                continue
            # Check agent ID
            if rule.agent_ids and agent_id not in rule.agent_ids:
                continue
            # Check keywords
            if rule.keywords and not any(kw.lower() in obj_lower for kw in rule.keywords):
                continue

            # Rule matched
            auto_approve = risk_score < rule.auto_approve_below_risk
            return RuleEvalResult(
                triggered=True,
                rule_id=rule.rule_id,
                rule_name=rule.name,
                auto_approve=auto_approve,
                reason=(
                    f"Auto-approved (risk={risk_score:.2f} < {rule.auto_approve_below_risk})"
                    if auto_approve else
                    f"Rule '{rule.name}' requires approval (risk={risk_score:.2f})"
                ),
                timeout_seconds=rule.timeout_seconds,
                timeout_default=rule.timeout_default,
            )

        return RuleEvalResult(
            triggered=False, rule_id=None, rule_name=None,
            auto_approve=True, reason="No matching approval rule — proceeding",
        )

    def list_rules(self, enabled_only: bool = True) -> list[ApprovalRule]:
        rules = list(self._rules.values())
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        return sorted(rules, key=lambda r: r.priority)

    def enable(self, rule_id: str) -> None:
        if rule := self._rules.get(rule_id):
            rule.enabled = True

    def disable(self, rule_id: str) -> None:
        if rule := self._rules.get(rule_id):
            rule.enabled = False

    def summary(self) -> dict[str, Any]:
        return {
            "total": len(self._rules),
            "enabled": sum(1 for r in self._rules.values() if r.enabled),
            "rules": [{"id": r.rule_id, "name": r.name, "priority": r.priority, "enabled": r.enabled}
                      for r in self.list_rules(enabled_only=False)],
        }

    # ------------------------------------------------------------------

    def _seed_defaults(self) -> None:
        defaults = [
            ApprovalRule(
                rule_id="exec_high_risk",
                name="High-risk EXECUTE action",
                description="Require approval for any EXECUTE action with risk >= 0.7",
                action_classes=["EXECUTE"],
                min_risk_score=0.7,
                auto_approve_below_risk=0.0,
                timeout_seconds=3600,
                timeout_default="reject",
                priority=10,
                tags=["security", "default"],
            ),
            ApprovalRule(
                rule_id="financial_execute",
                name="Financial execution",
                description="All financial execution requires human approval",
                action_classes=["EXECUTE"],
                keywords=["buy", "sell", "transfer", "payment", "invest", "wire", "withdraw"],
                min_risk_score=0.0,
                auto_approve_below_risk=0.0,
                timeout_seconds=86400,
                timeout_default="reject",
                priority=5,
                tags=["finance", "default"],
            ),
            ApprovalRule(
                rule_id="delete_operations",
                name="Destructive operations",
                description="Deletions, overwrites, and data destruction require approval",
                action_classes=["EXECUTE"],
                keywords=["delete", "remove", "destroy", "wipe", "format", "drop", "truncate"],
                min_risk_score=0.0,
                auto_approve_below_risk=0.0,
                timeout_seconds=3600,
                timeout_default="reject",
                priority=5,
                tags=["security", "default"],
            ),
            ApprovalRule(
                rule_id="external_communication",
                name="External communication",
                description="Sending emails/messages externally requires approval",
                action_classes=["EXECUTE", "DRAFT"],
                keywords=["send email", "send message", "post", "publish", "submit"],
                min_risk_score=0.0,
                auto_approve_below_risk=0.2,
                timeout_seconds=7200,
                timeout_default="reject",
                priority=20,
                tags=["communication", "default"],
            ),
            ApprovalRule(
                rule_id="exec_medium_risk",
                name="Medium-risk EXECUTE action",
                description="Medium-risk executions: auto-approve if risk < 0.5",
                action_classes=["EXECUTE"],
                min_risk_score=0.4,
                auto_approve_below_risk=0.5,
                timeout_seconds=1800,
                timeout_default="reject",
                priority=50,
                tags=["default"],
            ),
        ]
        for rule in defaults:
            self._rules[rule.rule_id] = rule
