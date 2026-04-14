"""
CEO Agent — top-level strategic executive.

Receives raw user intent, interprets it at a strategic level, selects the
operating mode, and produces a structured strategic brief for the Chief of Staff.
"""
from __future__ import annotations

import json
import logging

from sovereign.swarm.base_agent import AgentContext, AgentTask, BaseAgent
from sovereign.kernel.action_classes import ActionClass
from sovereign.output.output_contract import OutputStatus, StructuredOutput

logger = logging.getLogger(__name__)

OPERATING_MODES = [
    "command", "business", "personal", "finance",
    "study", "travel", "research", "builder",
    "local_offline", "survival",
]


class CEOAgent(BaseAgent):
    """
    The top-level executive agent.

    Responsibilities:
    - Interpret user intent at strategic level
    - Select the appropriate operating mode
    - Decompose intent into a high-level strategic brief
    - Set the action class ceiling for the session
    - Delegate to ChiefOfStaff for task decomposition

    Uses claude-opus-4-6 (frontier model) for highest reasoning quality.
    """

    agent_id = "ceo"
    model = "claude-opus-4-6"

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        """
        Process a user request as the CEO.

        Returns a StructuredOutput with:
          result:  The strategic brief text
          data:    {"operating_mode": str, "objectives": list[str], "action_class": str}
        """
        try:
            mode = await self._select_mode(task.objective, ctx)
            brief = await self._build_strategic_brief(task.objective, mode, ctx)

            return self._make_output(
                task=task,
                ctx=ctx,
                result=brief,
                status=OutputStatus.SUCCESS,
                data={
                    "operating_mode": mode,
                    "action_class": task.action_class.name,
                },
                reasoning=f"Mode selected: {mode}",
                confidence=0.85,
            )
        except Exception as exc:
            logger.error("CEOAgent failed", error=str(exc))
            return StructuredOutput.failure(
                session_id=ctx.session_id,
                agent_id=self.agent_id,
                task_id=task.task_id,
                error=str(exc),
            )

    async def _select_mode(self, objective: str, ctx: AgentContext) -> str:
        """
        Ask Claude to classify the user's objective into an operating mode.
        Uses a lightweight prompt on the fast model to minimise latency.
        """
        prompt = (
            f"Classify the following user request into exactly one operating mode.\n\n"
            f"Request: {objective}\n\n"
            f"Available modes: {', '.join(OPERATING_MODES)}\n\n"
            f"Reply with only the mode name, nothing else."
        )
        messages = [{"role": "user", "content": prompt}]
        raw = await self._call_claude(messages, ctx, max_tokens=20)
        mode = raw.strip().lower().replace("-", "_").split()[0]
        return mode if mode in OPERATING_MODES else ctx.operating_mode

    async def _build_strategic_brief(
        self,
        objective: str,
        mode: str,
        ctx: AgentContext,
    ) -> str:
        """
        Generate a structured strategic brief for the Chief of Staff.
        """
        prompt = (
            f"You are the CEO Agent of the SOVEREIGN AI OS.\n\n"
            f"Operating mode: {mode}\n"
            f"User request: {objective}\n\n"
            f"Produce a concise strategic brief with:\n"
            f"1. Restatement of the core objective\n"
            f"2. Key success criteria (2-3 bullet points)\n"
            f"3. Recommended next actions (2-4 bullet points)\n"
            f"4. Any constraints or risks to flag\n\n"
            f"Be sharp and executive. No fluff."
        )
        messages = [{"role": "user", "content": prompt}]
        return await self._call_claude(messages, ctx, task=None, max_tokens=512)
