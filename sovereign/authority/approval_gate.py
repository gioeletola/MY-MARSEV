"""
Human-in-the-loop approval gate.

Blocks EXECUTE-class (and any other threshold-exceeding) actions until a
human approves them, or the policy engine auto-decides.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

from sovereign.authority.thresholds import EscalationThresholds
from sovereign.kernel.action_classes import ActionClass

logger = logging.getLogger(__name__)


class ApprovalDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"


@dataclass
class ApprovalRequest:
    """Payload for a human approval request."""

    request_id: str
    agent_id: str
    action_class: ActionClass
    action_description: str
    context: dict[str, Any]
    risk_score: float = 0.5


@dataclass
class ApprovalResult:
    """Result returned by the approval gate."""

    decision: ApprovalDecision
    approver: str       # "human" | "auto-policy" | "guardian"
    rationale: str = ""


class ApprovalGate:
    """
    Approval gate with two modes:

    "cli"  — Interactive: prints the request to stdout and reads a y/n answer.
    "auto" — Policy-based: auto-approves below threshold, rejects above.
    """

    def __init__(
        self,
        mode: str = "cli",
        thresholds: EscalationThresholds | None = None,
    ) -> None:
        if mode not in ("cli", "auto"):
            raise ValueError(f"Unknown approval mode '{mode}'. Use 'cli' or 'auto'.")
        self._mode = mode
        self._thresholds = thresholds or EscalationThresholds()

    async def request_approval(self, req: ApprovalRequest) -> ApprovalResult:
        """
        Request approval for an action.

        In 'auto' mode: decides via policy rules.
        In 'cli' mode: prompts the human and waits for input.
        """
        logger.info(
            "Approval requested",
            agent=req.agent_id,
            action=req.action_description,
            risk=req.risk_score,
        )

        if self._mode == "auto":
            return self._auto_decide(req)
        else:
            return await self._cli_prompt(req)

    def _auto_decide(self, req: ApprovalRequest) -> ApprovalResult:
        """Apply threshold rules to auto-approve or auto-reject."""
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
        """
        Display the approval request to the terminal and read user input.
        """
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
