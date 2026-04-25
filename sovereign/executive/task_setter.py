"""Task Setter Agent — converts natural-language requests into structured task queues."""
from __future__ import annotations

import json
import logging

from sovereign.output.output_contract import OutputStatus, StructuredOutput
from sovereign.swarm.base_agent import AgentContext, AgentTask, BaseAgent

logger = logging.getLogger(__name__)


class TaskSetterAgent(BaseAgent):
    """
    Converts a user request or strategic brief into a structured task queue
    with dependencies, priorities, and assigned agent hints.
    """

    agent_id = "task_setter"
    model = "claude-sonnet-4-6"

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        try:
            task_queue = await self._build_queue(task.objective, ctx)
            return self._make_output(
                task=task,
                ctx=ctx,
                result=f"Task queue built: {len(task_queue)} tasks.",
                status=OutputStatus.SUCCESS,
                data={"task_queue": task_queue},
                confidence=0.80,
            )
        except Exception as exc:
            return StructuredOutput.failure(
                session_id=ctx.session_id,
                agent_id=self.agent_id,
                task_id=task.task_id,
                error=str(exc),
            )

    async def _build_queue(self, brief: str, ctx: AgentContext) -> list[dict]:
        prompt = (
            "You are the Task Setter of the SOVEREIGN AI OS.\n\n"
            f"Input: {brief}\n\n"
            "Convert this into a structured task queue as a JSON array.\n"
            "Each task: {id, objective, priority (1-5), dependencies: [], agent_hint, estimated_tokens}\n"
            "Return only the JSON array."
        )
        messages = [{"role": "user", "content": prompt}]
        raw = await self._call_claude(messages, ctx, max_tokens=1024)
        try:
            s = raw.find("[")
            e = raw.rfind("]") + 1
            return json.loads(raw[s:e]) if s >= 0 else []
        except Exception:
            return [{"id": "t1", "objective": brief, "priority": 3, "dependencies": [], "agent_hint": "worker"}]
