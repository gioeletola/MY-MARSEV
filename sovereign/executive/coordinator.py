"""Coordinator Agent — routes tasks from Chief of Staff to the right agents."""
from __future__ import annotations

import logging

from sovereign.output.output_contract import OutputStatus, StructuredOutput
from sovereign.swarm.base_agent import AgentContext, AgentTask, BaseAgent

logger = logging.getLogger(__name__)


class CoordinatorAgent(BaseAgent):
    """Routes tasks to the appropriate chief or worker agents."""

    agent_id = "coordinator"
    model = "claude-sonnet-4-6"

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        """Determine which agent should handle the task."""
        try:
            agent_hint = task.context.get("agent_hint", "worker")
            return self._make_output(
                task=task,
                ctx=ctx,
                result=f"Task routed to: {agent_hint}",
                status=OutputStatus.SUCCESS,
                data={"routed_to": agent_hint},
                confidence=0.75,
            )
        except Exception as exc:
            return StructuredOutput.failure(
                session_id=ctx.session_id,
                agent_id=self.agent_id,
                task_id=task.task_id,
                error=str(exc),
            )
