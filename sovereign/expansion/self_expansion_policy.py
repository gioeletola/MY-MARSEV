"""Self-expansion policy — safety rules governing autonomous agent promotion."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# Domains that always require a human to approve promotion (never auto-promote)
_HIGH_RISK_DOMAINS = frozenset({
    "financial", "finance", "legal", "security", "medical", "compliance",
    "executive", "payments", "trading", "investment",
})

# Action classes that can never be auto-promoted to production
_BLOCKED_AUTO_ACTION_CLASSES = frozenset({"EXECUTE"})

# Agent IDs that are permanently locked to sandbox/shadow
_LOCKED_AGENTS = frozenset({
    "ceo_agent", "chief_of_staff", "guardian", "approval_gate",
})


@dataclass
class PolicyRule:
    rule_id: str
    description: str
    enabled: bool = True


@dataclass
class PolicyDecision:
    allowed: bool
    rule_id: str
    reason: str


class SelfExpansionPolicy:
    """
    Evaluates whether an agent promotion is allowed under the current policy.

    Rules (evaluated in order — first blocking rule wins):
    1. Locked agents can never be promoted beyond sandbox
    2. High-risk domains require human approval (promoted_by != "auto")
    3. EXECUTE-class agents cannot be auto-promoted to production
    4. Custom rules registered at runtime
    """

    def __init__(self) -> None:
        self._rules: list[tuple[str, Any]] = []
        self._custom_blocked_domains: set[str] = set()
        self._require_human_for_production: bool = True

    # ------------------------------------------------------------------
    # Main API
    # ------------------------------------------------------------------

    def check_promotion(
        self,
        agent_id: str,
        domain: str,
        from_stage: Any,  # AgentStage
        promoted_by: str = "auto",
        action_class: str = "",
    ) -> tuple[bool, str]:
        """Return (allowed, reason). False blocks the promotion."""
        # Rule 1: Locked agents
        if agent_id in _LOCKED_AGENTS:
            return False, f"Agent '{agent_id}' is in the permanently locked set"

        # Rule 2: High-risk domain → human only
        dom = domain.lower()
        if dom in _HIGH_RISK_DOMAINS or dom in self._custom_blocked_domains:
            if promoted_by == "auto":
                return False, (
                    f"Domain '{domain}' is high-risk — requires human approval "
                    f"(promoted_by='auto' is not allowed)"
                )

        # Rule 3: EXECUTE class → human only for production
        if action_class in _BLOCKED_AUTO_ACTION_CLASSES:
            if promoted_by == "auto":
                return False, (
                    f"EXECUTE-class agents cannot be auto-promoted (action_class={action_class})"
                )

        # Rule 4: Human required for production stage (if flag set)
        from_stage_str = str(from_stage)
        if self._require_human_for_production and "shadow" in from_stage_str.lower():
            if promoted_by == "auto":
                return False, "Production promotion always requires human approval (policy flag set)"

        # Custom rules
        for rule_id, fn in self._rules:
            allowed, reason = fn(agent_id=agent_id, domain=domain,
                                 from_stage=from_stage, promoted_by=promoted_by)
            if not allowed:
                return False, f"[{rule_id}] {reason}"

        return True, "OK"

    def add_blocked_domain(self, domain: str) -> None:
        self._custom_blocked_domains.add(domain.lower())
        logger.info("SelfExpansionPolicy: blocked domain added: %s", domain)

    def set_require_human_for_production(self, value: bool) -> None:
        self._require_human_for_production = value

    def add_rule(self, rule_id: str, fn: Any) -> None:
        """Register a custom rule function: fn(agent_id, domain, from_stage, promoted_by) → (bool, str)."""
        self._rules.append((rule_id, fn))

    def summary(self) -> dict:
        return {
            "high_risk_domains": sorted(_HIGH_RISK_DOMAINS | self._custom_blocked_domains),
            "locked_agents": sorted(_LOCKED_AGENTS),
            "blocked_auto_action_classes": sorted(_BLOCKED_AUTO_ACTION_CLASSES),
            "require_human_for_production": self._require_human_for_production,
            "custom_rules": len(self._rules),
        }
