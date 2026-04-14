"""
Worker Agent — general-purpose execution agent.

Handles most concrete tasks: research, summarisation, drafting,
data transformation, tool-use operations. Uses claude-sonnet-4-6.
"""
from __future__ import annotations

import logging

from sovereign.swarm.base_agent import AgentContext, AgentTask, BaseAgent
from sovereign.output.output_contract import OutputStatus, StructuredOutput

logger = logging.getLogger(__name__)


class WorkerAgent(BaseAgent):
    """
    General-purpose worker. Receives a specific task objective and executes it,
    optionally using tools from its allowed tool list.
    """

    agent_id = "worker"
    model = "claude-sonnet-4-6"

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        """Execute the task, with or without tools depending on tools_allowed."""
        try:
            if task.tools_allowed:
                result_text, _ = await self._call_with_tools(
                    messages=[{"role": "user", "content": task.objective}],
                    ctx=ctx,
                    task=task,
                )
            else:
                result_text = await self._call_claude(
                    messages=[{"role": "user", "content": task.objective}],
                    ctx=ctx,
                    task=task,
                )

            return self._make_output(
                task=task,
                ctx=ctx,
                result=result_text,
                status=OutputStatus.SUCCESS,
                confidence=0.75,
            )
        except Exception as exc:
            logger.error("WorkerAgent failed", error=str(exc), task=task.task_id)
            return StructuredOutput.failure(
                session_id=ctx.session_id,
                agent_id=self.agent_id,
                task_id=task.task_id,
                error=str(exc),
            )
