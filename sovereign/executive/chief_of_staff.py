"""
Chief of Staff Agent — translates the CEO's strategic brief into actionable tasks.
"""
from __future__ import annotations

import logging

from sovereign.output.output_contract import OutputStatus, StructuredOutput
from sovereign.swarm.base_agent import AgentContext, AgentTask, BaseAgent

logger = logging.getLogger(__name__)


class ChiefOfStaff(BaseAgent):
    """
    Receives the CEO's strategic brief and decomposes it into a prioritised
    task list. Assigns tasks to coordinators or worker agents.
    """

    agent_id = "chief_of_staff"
    model = "claude-sonnet-4-6"

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        """Decompose strategic brief into tasks and return them."""
        try:
            tasks = await self._decompose(task.objective, ctx)
            return self._make_output(
                task=task,
                ctx=ctx,
                result=f"Decomposed into {len(tasks)} tasks.",
                status=OutputStatus.SUCCESS,
                data={"tasks": tasks},
                confidence=0.80,
            )
        except Exception as exc:
            logger.error("ChiefOfStaff failed", error=str(exc))
            return StructuredOutput.failure(
                session_id=ctx.session_id,
                agent_id=self.agent_id,
                task_id=task.task_id,
                error=str(exc),
            )

    async def _decompose(self, brief: str, ctx: AgentContext) -> list[dict]:
        """Ask Claude to break the brief into a task list."""
        prompt = (
            f"You are the Chief of Staff of the SOVEREIGN AI OS.\n\n"
            f"Strategic brief:\n{brief}\n\n"
            f"Break this down into a prioritised list of specific, actionable tasks.\n"
            f"For each task output a JSON object with: objective, priority (1-5), agent_hint.\n"
            f"Return a JSON array of task objects only. No prose."
        )
        messages = [{"role": "user", "content": prompt}]
        raw = await self._call_claude(messages, ctx, max_tokens=1024)
        import json
        try:
            # Extract JSON from the response
            start = raw.find("[")
            end = raw.rfind("]") + 1
            return json.loads(raw[start:end]) if start >= 0 else []
        except Exception:
            return [{"objective": brief, "priority": 3, "agent_hint": "worker"}]
