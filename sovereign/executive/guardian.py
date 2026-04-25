"""
Guardian Agent — safety enforcer.

Reviews all EXECUTE-class actions before dispatch. Can approve, veto,
or downgrade the action class. Triggers human escalation when risk is high.

Upgraded to AgentLevel.LEVEL_3: full 7-step operational workflow with
structured AgentSpec metadata and explicit ApprovalGate integration.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from sovereign.kernel.action_classes import ActionClass
from sovereign.output.output_contract import OutputStatus, StructuredOutput
from sovereign.swarm.base_agent import AgentContext, AgentTask
from sovereign.swarm.leveled_agent import AgentLevel, AgentSpec, LeveledAgent

logger = logging.getLogger(__name__)


class GuardianAgent(LeveledAgent):
    """
    Runs on claude-sonnet-4-6 with a safety-focused system prompt.

    LEVEL_3 Autonomous Operational Agent — acts as the safety gate for
    all EXECUTE-class actions in the swarm.

    Called synchronously in the agent dispatch path before any EXECUTE
    action.  The Guardian never raises; it always returns a StructuredOutput
    with approved=True/False so the orchestrator can gate on it.

    Workflow steps:
      OBSERVE   — extract action class and context from the task
      ANALYZE   — run pre-flight policy registry check (if available)
      PLAN      — skip (not applicable for safety reviews)
      EXECUTE   — call Claude to assess risk; check ActionClass >= EXECUTE;
                  verify against constitution
      VERIFY    — confirm the decision is internally consistent
      REPORT    — assemble approve/block StructuredOutput
      SAVE_MEM  — record the decision in agent state history
    """

    agent_id = "guardian"
    model = "claude-sonnet-4-6"

    spec = AgentSpec(
        agent_id="guardian",
        level=AgentLevel.LEVEL_3,
        mission="Safety review and approval gating for all EXECUTE-class actions",
        triggers=["execute_action", "approval_request"],
        tools_allowed=["memory_tool"],
        escalate_to="ceo",
        requires_approval_for=[
            "external_api_call",
            "file_deletion",
            "send_message",
            "code_execution",
        ],
        success_metric="No unsafe actions pass through",
        failure_condition="False positive blocks > 10% of safe actions",
        confidence_threshold=0.9,
    )

    # ------------------------------------------------------------------
    # Injected dependencies (optional, set post-construction)
    # ------------------------------------------------------------------

    def set_policy_registry(self, policy_registry: Any) -> None:
        """Inject a PolicyRegistry for pre-flight rule evaluation."""
        self._policy_registry = policy_registry

    # ------------------------------------------------------------------
    # Workflow step overrides
    # ------------------------------------------------------------------

    async def observe(self, task: AgentTask, ctx: AgentContext) -> dict:
        """
        OBSERVE: extract the action class and surface the task context.
        """
        return {
            "objective": task.objective,
            "action_class": task.action_class.name,
            "action_class_value": task.action_class.value,
            "operating_mode": ctx.operating_mode,
            "session_id": ctx.session_id,
        }

    async def analyze(
        self, task: AgentTask, ctx: AgentContext, observations: dict
    ) -> dict:
        """
        ANALYZE: run pre-flight policy registry check if available.

        For READ and SUGGEST actions, auto-approve without calling Claude.
        For higher classes, run policy-registry evaluation.
        """
        action_class = task.action_class

        # Auto-approve low-risk action classes
        if action_class <= ActionClass.SUGGEST:
            return {
                "auto_approved": True,
                "policy_action": "allow",
                "policy_rationale": "Auto-approved: action class is READ or SUGGEST.",
                "risk_score": 0.1,
            }

        # Pre-flight policy registry check
        policy_ctx = {
            "action_class": action_class.name,
            "mode": ctx.operating_mode,
            "objective": task.objective,
            "_in_action_class": [action_class.name],
            "_in_mode": [ctx.operating_mode],
        }
        if hasattr(self, "_policy_registry") and self._policy_registry is not None:
            try:
                policy_action, policy_rationale = self._policy_registry.evaluate(
                    policy_ctx
                )
                return {
                    "auto_approved": False,
                    "policy_action": policy_action,
                    "policy_rationale": policy_rationale,
                    "risk_score": 1.0 if policy_action == "deny" else 0.85,
                }
            except Exception as exc:
                logger.warning("Policy registry evaluation failed: %s", exc)

        return {
            "auto_approved": False,
            "policy_action": "pending",
            "policy_rationale": "No policy match — proceeding to Claude review.",
            "risk_score": 0.5,
        }

    async def execute(
        self, task: AgentTask, ctx: AgentContext, plan: dict
    ) -> dict:
        """
        EXECUTE: perform the core safety review.

        For EXECUTE-class actions, verify against constitution and call
        Claude to assess risk.  Actions flagged in ``requires_approval_for``
        are additionally marked as requiring ApprovalGate sign-off.

        Steps:
          1. Check ActionClass level — gate on EXECUTE or higher.
          2. Verify against constitution (if available).
          3. Call Claude for AI risk assessment.
          4. Flag any action types requiring explicit approval.
        """
        analysis = plan  # plan step is skipped; plan dict = analyze output

        # Short-circuit for auto-approved actions
        if analysis.get("auto_approved"):
            return {
                "approved": True,
                "risk_score": analysis.get("risk_score", 0.1),
                "rationale": analysis.get("policy_rationale", "Auto-approved."),
                "requires_approval_gate": False,
                "action_class": task.action_class.name,
            }

        # Policy hard-deny
        if analysis.get("policy_action") == "deny":
            return {
                "approved": False,
                "risk_score": 1.0,
                "rationale": f"Policy DENY: {analysis.get('policy_rationale', '')}",
                "requires_approval_gate": False,
                "action_class": task.action_class.name,
            }

        # Policy escalate
        if analysis.get("policy_action") == "escalate":
            return {
                "approved": False,
                "risk_score": 0.85,
                "rationale": f"Policy ESCALATE: {analysis.get('policy_rationale', '')}",
                "requires_approval_gate": True,
                "action_class": task.action_class.name,
            }

        # Constitution check (EXECUTE+ class)
        if task.action_class >= ActionClass.EXECUTE:
            if hasattr(self, "_constitution") and self._constitution is not None:
                try:
                    # Constitution.check() returns (ok: bool, reason: str) if it exists
                    result = getattr(self._constitution, "check", None)
                    if callable(result):
                        ok, reason = result(task.objective, task.action_class)
                        if not ok:
                            return {
                                "approved": False,
                                "risk_score": 0.9,
                                "rationale": f"Constitution violation: {reason}",
                                "requires_approval_gate": True,
                                "action_class": task.action_class.name,
                            }
                except Exception as exc:
                    logger.warning("Constitution check failed: %s", exc)

        # AI risk assessment via Claude
        approved, risk_score, rationale = await self._review(task, ctx)

        # Flag specific action types that always require ApprovalGate
        requires_gate = any(
            kw in task.objective.lower()
            for kw in ("delete", "send", "execute", "api call", "deploy")
        )

        return {
            "approved": approved,
            "risk_score": risk_score,
            "rationale": rationale,
            "requires_approval_gate": requires_gate,
            "action_class": task.action_class.name,
        }

    async def verify(
        self, task: AgentTask, ctx: AgentContext, execution: dict
    ) -> dict:
        """
        VERIFY: check the safety decision is internally consistent.

        A decision is inconsistent if it approves a very high risk score
        or if the rationale is missing.
        """
        approved = execution.get("approved", False)
        risk_score = execution.get("risk_score", 0.5)
        rationale = execution.get("rationale", "")
        consistent = True
        warnings: list[str] = []

        if approved and risk_score > 0.7:
            warnings.append(
                f"High risk score {risk_score:.2f} but action approved — review manually."
            )
            consistent = False

        if not rationale:
            warnings.append("Missing rationale in safety decision.")
            consistent = False

        return {
            "consistent": consistent,
            "warnings": warnings,
        }

    async def report(
        self, task: AgentTask, ctx: AgentContext, all_steps: dict
    ) -> StructuredOutput:
        """
        REPORT: assemble the final approve / block StructuredOutput.
        """
        execution = all_steps.get("execute", {})
        verification = all_steps.get("verify", {})

        approved = execution.get("approved", False)
        risk_score = execution.get("risk_score", 0.5)
        rationale = execution.get("rationale", "No rationale available.")
        warnings = verification.get("warnings", [])

        status = OutputStatus.SUCCESS if approved else OutputStatus.ESCALATED
        if warnings:
            rationale += f" [Warnings: {'; '.join(warnings)}]"

        return self._make_output(
            task=task,
            ctx=ctx,
            result=rationale,
            status=status,
            data={
                "approved": approved,
                "risk_score": risk_score,
                "action_class": execution.get("action_class", task.action_class.name),
                "requires_approval_gate": execution.get("requires_approval_gate", False),
            },
            reasoning=rationale,
            confidence=0.9,
        )

    # ------------------------------------------------------------------
    # Convenience method for the orchestrator (unchanged interface)
    # ------------------------------------------------------------------

    async def review_action(
        self,
        agent_id: str,
        action_description: str,
        action_class: ActionClass,
        context: dict,
        ctx: AgentContext,
    ) -> tuple[bool, float, str]:
        """
        Convenience method for the orchestrator to review a specific action.

        Returns:
            (approved: bool, risk_score: float, rationale: str)
        """
        # For READ and SUGGEST, auto-approve without calling Claude
        if action_class <= ActionClass.SUGGEST:
            return True, 0.1, "Auto-approved: action class is READ or SUGGEST."

        # Pre-flight: check policy registry before calling Claude
        policy_ctx = {
            "action_class": action_class.name,
            "mode": ctx.operating_mode,
            "objective": action_description,
            "agent_id": agent_id,
            "_in_action_class": [action_class.name],
            "_in_mode": [ctx.operating_mode],
        }
        if hasattr(self, "_policy_registry") and self._policy_registry is not None:
            policy_action, policy_rationale = self._policy_registry.evaluate(policy_ctx)
            if policy_action == "deny":
                return False, 1.0, f"Policy DENY: {policy_rationale}"
            if policy_action == "escalate":
                return False, 0.85, f"Policy ESCALATE: {policy_rationale}"

        fake_task = AgentTask(
            objective=(
                f"Review action from agent '{agent_id}':\n"
                f"Action class: {action_class.name}\n"
                f"Description: {action_description}\n"
                f"Context: {context}"
            ),
            action_class=ActionClass.READ,
        )
        result = await self.run(fake_task, ctx)
        data = result.data
        return (
            data.get("approved", False),
            data.get("risk_score", 0.5),
            result.result,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _review(
        self,
        task: AgentTask,
        ctx: AgentContext,
    ) -> tuple[bool, float, str]:
        """Ask Claude to assess risk and approve/reject the action."""
        prompt = (
            "You are the Guardian Agent of the SOVEREIGN AI OS.\n"
            "Your role: assess whether the following action is safe and aligned.\n\n"
            f"Action to review:\n{task.objective}\n\n"
            f"Action class: {task.action_class.name}\n"
            f"Operating mode: {ctx.operating_mode}\n\n"
            "Respond with a JSON object:\n"
            '{"approved": true/false, "risk_score": 0.0-1.0, "rationale": "..."}\n'
            "Be strict. When in doubt, reject."
        )
        messages = [{"role": "user", "content": prompt}]
        raw = await self._call_claude(messages, ctx, max_tokens=256)

        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            data = json.loads(raw[start:end])
            return (
                bool(data.get("approved", False)),
                float(data.get("risk_score", 0.5)),
                str(data.get("rationale", raw)),
            )
        except Exception:
            # Fail closed on parse errors
            return False, 0.8, f"Guardian parse error — defaulting to reject. Raw: {raw[:200]}"
