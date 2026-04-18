"""
Guardian Agent — safety enforcer.

Reviews all EXECUTE-class actions before dispatch. Can approve, veto,
or downgrade the action class. Triggers human escalation when risk is high.
"""
from __future__ import annotations

import logging

from typing import Any

from sovereign.swarm.base_agent import AgentContext, AgentTask, BaseAgent
from sovereign.kernel.action_classes import ActionClass
from sovereign.output.output_contract import OutputStatus, StructuredOutput

logger = logging.getLogger(__name__)


class GuardianAgent(BaseAgent):
    """
    Runs on claude-sonnet-4-6 with a safety-focused system prompt.
    Called synchronously in the agent dispatch path before any EXECUTE action.
    """

    agent_id = "guardian"
    model = "claude-sonnet-4-6"

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        """Run a safety review for the task described in task.objective."""
        try:
            approved, risk_score, rationale = await self._review(task, ctx)
            return self._make_output(
                task=task,
                ctx=ctx,
                result=rationale,
                status=OutputStatus.SUCCESS if approved else OutputStatus.ESCALATED,
                data={
                    "approved": approved,
                    "risk_score": risk_score,
                    "action_class": task.action_class.name,
                },
                reasoning=rationale,
                confidence=0.9,
            )
        except Exception as exc:
            logger.error("GuardianAgent failed", error=str(exc))
            return StructuredOutput.failure(
                session_id=ctx.session_id,
                agent_id=self.agent_id,
                task_id=task.task_id,
                error=str(exc),
                requires_human_review=True,
            )

    def set_policy_registry(self, policy_registry: Any) -> None:
        """Inject a PolicyRegistry for pre-flight rule evaluation."""
        self._policy_registry = policy_registry

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

        import json
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
