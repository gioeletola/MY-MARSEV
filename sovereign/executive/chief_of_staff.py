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
        mode = ctx.operating_mode
        prompt = (
            f"You are the Chief of Staff of the SOVEREIGN AI OS, operating in {mode!r} mode.\n\n"
            f"Strategic brief from CEO:\n{brief}\n\n"
            "Decompose this into 1–5 specific, parallel-executable tasks.\n"
            "Rules:\n"
            "- Tasks should be independent where possible (no unnecessary serialisation)\n"
            "- Use agent_hint to suggest the best specialist agent\n"
            "- Priority 1=critical, 3=normal, 5=background\n"
            "- Include estimated_tokens (100-2000) based on complexity\n"
            "- Include depends_on (list of task indices, 0-based) for sequential tasks\n\n"
            "Return ONLY a JSON array, no prose:\n"
            '[{"objective": "...", "priority": 3, "agent_hint": "worker", '
            '"estimated_tokens": 500, "depends_on": []}]'
        )
        messages = [{"role": "user", "content": prompt}]
        raw = await self._call_claude(messages, ctx, max_tokens=1500)
        import json
        try:
            start = raw.find("[")
            end = raw.rfind("]") + 1
            tasks = json.loads(raw[start:end]) if start >= 0 else []
            # Validate and normalise fields
            for t in tasks:
                t.setdefault("priority", 3)
                t.setdefault("agent_hint", "worker")
                t.setdefault("estimated_tokens", 500)
                t.setdefault("depends_on", [])
            return tasks or [{"objective": brief, "priority": 3, "agent_hint": "worker",
                               "estimated_tokens": 500, "depends_on": []}]
        except Exception:
            return [{"objective": brief, "priority": 3, "agent_hint": "worker",
                     "estimated_tokens": 500, "depends_on": []}]
