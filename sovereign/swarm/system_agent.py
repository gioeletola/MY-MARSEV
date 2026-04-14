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
        # Stub: return a basic health check
        return self._make_output(
            task=task,
            ctx=ctx,
            result="System health: OK",
            status=OutputStatus.SUCCESS,
            data={"health": "ok", "checks": ["memory", "tools", "policy"]},
            confidence=1.0,
        )
