"""Decision Brief Agent — generates structured decision memos for human review."""
from __future__ import annotations

import logging

from sovereign.output.output_contract import OutputStatus, StructuredOutput
from sovereign.swarm.base_agent import AgentContext, AgentTask, BaseAgent

logger = logging.getLogger(__name__)


class DecisionBriefAgent(BaseAgent):
    """
    Produces an approval brief with: context, options, recommendation,
    risk, cost, reversibility, expected upside/downside, deadline.
    """

    agent_id = "decision_brief"
    model = "claude-opus-4-7"

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        """Generate a decision brief for the situation described in task.objective."""
        try:
            brief = await self._generate(task.objective, ctx)
            return self._make_output(
                task=task,
                ctx=ctx,
                result=brief,
                status=OutputStatus.PENDING_APPROVAL,
                requires_human_review=True,
                confidence=0.9,
            )
        except Exception as exc:
            return StructuredOutput.failure(
                session_id=ctx.session_id,
                agent_id=self.agent_id,
                task_id=task.task_id,
                error=str(exc),
            )

    async def _generate(self, situation: str, ctx: AgentContext) -> str:
        prompt = (
            "You are the Decision Brief Agent of the SOVEREIGN AI OS.\n"
            "Produce a concise decision brief for the following situation.\n\n"
            f"Situation: {situation}\n\n"
            "Structure:\n"
            "1. Decision Title\n"
            "2. Context (2-3 sentences)\n"
            "3. Options (2-3 options with pros/cons)\n"
            "4. Recommended Option + Why\n"
            "5. Risk level (Low / Medium / High) + Rationale\n"
            "6. Reversibility\n"
            "7. Expected Upside / Downside\n"
            "8. What happens if delayed\n\n"
            "Be precise and executive."
        )
        messages = [{"role": "user", "content": prompt}]
        return await self._call_claude(messages, ctx, max_tokens=1024)
