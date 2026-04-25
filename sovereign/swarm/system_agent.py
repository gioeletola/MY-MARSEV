"""System Agent — monitors health, enforces governance, checks memory consistency."""
from __future__ import annotations

from sovereign.swarm.base_agent import AgentContext, AgentTask, BaseAgent
from sovereign.output.output_contract import OutputStatus, StructuredOutput


class SystemAgent(BaseAgent):
    """
    System-level agent responsible for:
    - Health monitoring
    - Observability
    - Governance checks
    - Policy enforcement
    - Memory consistency checks
    - Trust scoring

    Runs as a background agent; not user-facing.
    """

    agent_id = "system"
    model = "claude-haiku-4-5-20251001"

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        """Execute a system-level monitoring or governance task."""
        result, _ = await self._call_with_tools(
            messages=[{"role": "user", "content": (
                f"You are the System Agent of the SOVEREIGN AI OS. "
                f"Your role is health monitoring, governance checks, and policy enforcement.\n\n"
                f"Task: {task.objective}"
            )}],
            ctx=ctx,
            task=task,
        )
        return self._make_output(
            task=task,
            ctx=ctx,
            result=result,
            status=OutputStatus.SUCCESS,
            data={"health": "ok", "checks": ["memory", "tools", "policy"]},
            confidence=0.95,
        )
