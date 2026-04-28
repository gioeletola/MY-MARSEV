"""
Human-in-the-loop approval gate.

Supports four modes:
  AUTO    — approve everything automatically (dev/test)
  CLI     — interactive terminal prompt
  POLICY  — rule-based auto-approval
  WEBHOOK — call external URL for decision

Public API:
  gate = ApprovalGate.from_env()
  decision = await gate.request_approval(action, context, user_id)
  gate.register_auto_rule(condition_fn, outcome)
  gate.audit_trail   → list of all decisions
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from sovereign.authority.thresholds import EscalationThresholds
from sovereign.kernel.action_classes import ActionClass

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ApprovalMode(str, Enum):
    AUTO    = "auto"
    CLI     = "cli"
    POLICY  = "policy"
    WEBHOOK = "webhook"


# ---------------------------------------------------------------------------
# Legacy enum (kept for backward compatibility)
# ---------------------------------------------------------------------------

class ApprovalDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ApprovalRequest:
    """Payload for an approval request (legacy dataclass)."""
    request_id: str
    agent_id: str
    action_class: ActionClass
    action_description: str
    context: dict[str, Any]
    risk_score: float = 0.5


@dataclass
class ApprovalResult:
    """Result returned by the approval gate (legacy dataclass)."""
    decision: ApprovalDecision
    approver: str       # "human" | "auto-policy" | "guardian" | "webhook"
    rationale: str = ""


@dataclass
class ApprovalDecisionRecord:
    """
    Rich approval decision record used by the new API.

    Attributes:
        approved   – True if the action was approved
        reason     – Human-readable explanation
        approver   – Who/what made the decision
        timestamp  – ISO-8601 UTC string
        action_id  – Unique ID for this approval request
    """
    approved: bool
    reason: str
    approver: str
    timestamp: str
    action_id: str
    action: str = ""
    user_id: str = ""
    context: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Built-in policy rule helpers
# ---------------------------------------------------------------------------

def _is_read_action(action: str, context: dict, user_id: str) -> bool | None:
    """Always approve READ actions."""
    if action.lower() in ("read", "list", "get", "view", "search", "query"):
        return True
    return None


def _is_admin_user(action: str, context: dict, user_id: str) -> bool | None:
    """Always approve requests from known admin users."""
    admin_users = {"admin", "system", "sovereign", "ceo_agent"}
    if user_id in admin_users:
        return True
    return None


def _financial_limit(action: str, context: dict, user_id: str) -> bool | None:
    """Require approval for financial operations above $1000."""
    amount = context.get("amount", 0)
    if action.lower() in ("payment", "transfer", "invest", "withdraw", "financial_op"):
        if isinstance(amount, (int, float)) and amount > 1000:
            return False     # deny automatically → escalate to human
    return None


# ---------------------------------------------------------------------------
# ApprovalGate
# ---------------------------------------------------------------------------

class ApprovalGate:
    """
    Approval gate with four modes: AUTO, CLI, POLICY, WEBHOOK.

    New API:
        gate = ApprovalGate.from_env()
        decision: ApprovalDecisionRecord = await gate.request_approval(
            action="execute_trade",
            context={"amount": 5000},
            user_id="alice",
        )

    Legacy API (still works):
        result: ApprovalResult = await gate.request_approval(req: ApprovalRequest)
    """

    def __init__(
        self,
        mode: str | ApprovalMode = ApprovalMode.CLI,
        thresholds: EscalationThresholds | None = None,
        webhook_url: str | None = None,
    ) -> None:
        mode_val = ApprovalMode(mode) if isinstance(mode, str) else mode
        self._mode = mode_val
        self._thresholds = thresholds or EscalationThresholds()
        self._webhook_url = webhook_url
        self._audit: list[ApprovalDecisionRecord] = []
        # Policy rules: list of (condition_fn, outcome)
        # condition_fn(action, context, user_id) -> bool | None
        # outcome: True = approve, False = reject, None = skip this rule
        self._policy_rules: list[tuple[Callable, bool]] = []
        # Register built-in rules
        self._register_builtin_rules()

    # -------------------------------------------------------------------------
    # Factory
    # -------------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> ApprovalGate:
        """
        Build an ApprovalGate from environment variables.

        SOVEREIGN_APPROVAL_MODE — auto|cli|policy|webhook (default: cli)
        SOVEREIGN_WEBHOOK_URL   — required when mode=webhook
        """
        mode_str = os.environ.get("SOVEREIGN_APPROVAL_MODE", "cli").lower()
        try:
            mode = ApprovalMode(mode_str)
        except ValueError:
            logger.warning("Unknown SOVEREIGN_APPROVAL_MODE=%r, defaulting to CLI", mode_str)
            mode = ApprovalMode.CLI
        webhook_url = os.environ.get("SOVEREIGN_WEBHOOK_URL")
        return cls(mode=mode, webhook_url=webhook_url)

    # -------------------------------------------------------------------------
    # Rule management
    # -------------------------------------------------------------------------

    def _register_builtin_rules(self) -> None:
        """Register the default policy rules."""
        # Read always passes
        self.register_auto_rule(
            lambda action, ctx, uid: True if action.lower() in ("read", "list", "get", "view", "search", "query") else None,
            outcome=True,
        )
        # Admin users always pass
        self.register_auto_rule(
            lambda action, ctx, uid: True if uid in {"admin", "system", "sovereign", "ceo_agent"} else None,
            outcome=True,
        )
        # Financial ops > $1000 require human approval (reject auto)
        self.register_auto_rule(
            lambda action, ctx, uid: (
                False if (
                    action.lower() in ("payment", "transfer", "invest", "withdraw", "financial_op")
                    and isinstance(ctx.get("amount", 0), (int, float))
                    and ctx.get("amount", 0) > 1000
                ) else None
            ),
            outcome=False,
        )

    def register_auto_rule(
        self,
        condition_fn: Callable[[str, dict, str], bool | None],
        outcome: bool,
    ) -> None:
        """
        Add a policy rule for auto-approval/rejection.

        condition_fn(action, context, user_id) must return:
          True  → apply the outcome (approve/reject)
          None  → skip this rule (try next)
          False → same as None (skip)

        outcome: True = approve, False = reject
        """
        self._policy_rules.append((condition_fn, outcome))

    # -------------------------------------------------------------------------
    # Main entry point
    # -------------------------------------------------------------------------

    async def request_approval(
        self,
        action_or_req: str | ApprovalRequest,
        context: dict | None = None,
        user_id: str = "unknown",
        timeout_seconds: int = 30,
    ) -> ApprovalDecisionRecord | ApprovalResult:
        """
        Request approval for an action.

        New API: pass action (str), context (dict), user_id (str)
        Legacy API: pass an ApprovalRequest instance
        """
        # Legacy path
        if isinstance(action_or_req, ApprovalRequest):
            return await self._legacy_request(action_or_req)

        # New path
        action = action_or_req
        ctx = context or {}
        action_id = str(uuid.uuid4())[:10]

        logger.info(
            "Approval requested: action=%s user=%s mode=%s id=%s",
            action, user_id, self._mode.value, action_id,
        )

        if self._mode == ApprovalMode.AUTO:
            decision = self._decide_auto(action_id, action, ctx, user_id)
        elif self._mode == ApprovalMode.POLICY:
            decision = self._decide_policy(action_id, action, ctx, user_id)
        elif self._mode == ApprovalMode.WEBHOOK:
            decision = await self._decide_webhook(action_id, action, ctx, user_id, timeout_seconds)
        else:  # CLI
            decision = await self._decide_cli(action_id, action, ctx, user_id, timeout_seconds)

        self._audit.append(decision)
        log_fn = logger.info if decision.approved else logger.warning
        log_fn("Approval %s: action=%s user=%s reason=%s",
               "GRANTED" if decision.approved else "DENIED",
               action, user_id, decision.reason)
        return decision

    # -------------------------------------------------------------------------
    # Decision strategies
    # -------------------------------------------------------------------------

    def _decide_auto(
        self, action_id: str, action: str, context: dict, user_id: str
    ) -> ApprovalDecisionRecord:
        """AUTO mode — approve everything."""
        return ApprovalDecisionRecord(
            approved=True,
            reason="AUTO mode: all actions approved",
            approver="auto",
            timestamp=datetime.now(timezone.utc).isoformat(),
            action_id=action_id,
            action=action,
            user_id=user_id,
            context=context,
        )

    def _decide_policy(
        self, action_id: str, action: str, context: dict, user_id: str
    ) -> ApprovalDecisionRecord:
        """POLICY mode — run registered rules in order."""
        for rule_fn, outcome in self._policy_rules:
            try:
                triggered = rule_fn(action, context, user_id)
                if triggered is True:
                    return ApprovalDecisionRecord(
                        approved=outcome,
                        reason=f"Policy rule matched: {'approved' if outcome else 'rejected'}",
                        approver="policy-engine",
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        action_id=action_id,
                        action=action,
                        user_id=user_id,
                        context=context,
                    )
            except Exception as exc:
                logger.warning("Policy rule error: %s", exc)

        # No rule matched → use threshold-based decision on risk_score from context
        risk = float(context.get("risk_score", 0.5))
        approved = self._thresholds.should_auto_approve(risk)
        return ApprovalDecisionRecord(
            approved=approved,
            reason=f"Policy default: risk_score={risk:.2f} threshold={self._thresholds.auto_approve_below_risk:.2f}",
            approver="policy-engine",
            timestamp=datetime.now(timezone.utc).isoformat(),
            action_id=action_id,
            action=action,
            user_id=user_id,
            context=context,
        )

    async def _decide_cli(
        self, action_id: str, action: str, context: dict, user_id: str, timeout: int
    ) -> ApprovalDecisionRecord:
        """CLI mode — interactive terminal prompt with timeout."""
        print("\n" + "=" * 60)
        print("APPROVAL REQUIRED")
        print("=" * 60)
        print(f"Action ID: {action_id}")
        print(f"Action:    {action}")
        print(f"User:      {user_id}")
        if context:
            for k, v in list(context.items())[:8]:
                print(f"  {k}: {v}")
        print(f"Timeout:   {timeout}s")
        print("=" * 60)

        try:
            answer = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, lambda: input("Approve? [y/N]: ").strip().lower()
                ),
                timeout=timeout,
            )
        except (asyncio.TimeoutError, EOFError, KeyboardInterrupt):
            answer = "n"

        approved = answer in ("y", "yes")
        return ApprovalDecisionRecord(
            approved=approved,
            reason="Human approved via CLI." if approved else "Human rejected via CLI (or timed out).",
            approver="human",
            timestamp=datetime.now(timezone.utc).isoformat(),
            action_id=action_id,
            action=action,
            user_id=user_id,
            context=context,
        )

    async def _decide_webhook(
        self, action_id: str, action: str, context: dict, user_id: str, timeout: int
    ) -> ApprovalDecisionRecord:
        """WEBHOOK mode — POST to external URL and await JSON response."""
        if not self._webhook_url:
            logger.error("ApprovalGate WEBHOOK mode but no webhook_url configured; defaulting to reject")
            return ApprovalDecisionRecord(
                approved=False,
                reason="Webhook URL not configured",
                approver="webhook-error",
                timestamp=datetime.now(timezone.utc).isoformat(),
                action_id=action_id,
                action=action,
                user_id=user_id,
                context=context,
            )
        try:
            import urllib.request
            import json
            payload = json.dumps({
                "action_id": action_id,
                "action": action,
                "user_id": user_id,
                "context": context,
            }).encode()
            req = urllib.request.Request(
                self._webhook_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
            approved = bool(data.get("approved", False))
            reason = data.get("reason", "Webhook decision")
            approver = data.get("approver", "webhook")
        except Exception as exc:
            logger.error("Webhook approval error: %s", exc)
            approved = False
            reason = f"Webhook error: {exc}"
            approver = "webhook-error"

        return ApprovalDecisionRecord(
            approved=approved,
            reason=reason,
            approver=approver,
            timestamp=datetime.now(timezone.utc).isoformat(),
            action_id=action_id,
            action=action,
            user_id=user_id,
            context=context,
        )

    # -------------------------------------------------------------------------
    # Legacy path
    # -------------------------------------------------------------------------

    async def _legacy_request(self, req: ApprovalRequest) -> ApprovalResult:
        """Handle the old ApprovalRequest → ApprovalResult path."""
        logger.info(
            "Approval requested (legacy): agent=%s action=%s risk=%.2f",
            req.agent_id, req.action_description, req.risk_score,
        )
        if self._mode in (ApprovalMode.AUTO, ApprovalMode.POLICY):
            return self._auto_decide(req)
        return await self._cli_prompt(req)

    def _auto_decide(self, req: ApprovalRequest) -> ApprovalResult:
        if self._thresholds.should_auto_approve(req.risk_score):
            return ApprovalResult(
                decision=ApprovalDecision.APPROVED,
                approver="auto-policy",
                rationale=f"Risk score {req.risk_score:.2f} below auto-approve threshold.",
            )
        return ApprovalResult(
            decision=ApprovalDecision.REJECTED,
            approver="auto-policy",
            rationale=(
                f"Risk score {req.risk_score:.2f} exceeds threshold "
                f"{self._thresholds.auto_approve_below_risk:.2f}."
            ),
        )

    async def _cli_prompt(self, req: ApprovalRequest) -> ApprovalResult:
        print("\n" + "=" * 60)
        print("APPROVAL REQUIRED")
        print("=" * 60)
        print(f"Agent:       {req.agent_id}")
        print(f"Action:      {req.action_description}")
        print(f"Class:       {req.action_class.name}")
        print(f"Risk score:  {req.risk_score:.2f}")
        if req.context:
            print(f"Context:     {req.context}")
        print("=" * 60)

        try:
            answer = input("Approve? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = "n"

        if answer in ("y", "yes"):
            return ApprovalResult(
                decision=ApprovalDecision.APPROVED,
                approver="human",
                rationale="Human approved via CLI.",
            )
        return ApprovalResult(
            decision=ApprovalDecision.REJECTED,
            approver="human",
            rationale="Human rejected via CLI.",
        )

    # -------------------------------------------------------------------------
    # Observability
    # -------------------------------------------------------------------------

    @property
    def audit_trail(self) -> list[ApprovalDecisionRecord]:
        """List of all approval decisions made by this gate."""
        return list(self._audit)

    @property
    def mode(self) -> ApprovalMode:
        return self._mode

    def stats(self) -> dict:
        total = len(self._audit)
        approved = sum(1 for d in self._audit if d.approved)
        return {
            "total": total,
            "approved": approved,
            "rejected": total - approved,
            "approval_rate": round(approved / total, 3) if total else 0.0,
            "mode": self._mode.value,
        }
