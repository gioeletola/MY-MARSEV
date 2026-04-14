"""Orchestrator Agent — routes work, breaks it into sub-problems, coordinates execution."""
from __future__ import annotations

from sovereign.swarm.base_agent import AgentContext, AgentTask, BaseAgent
from sovereign.output.output_contract import OutputStatus, StructuredOutput


class OrchestratorAgent(BaseAgent):
    """
    Mid-tier orchestration agent. Receives complex tasks from the executive layer
    and further decomposes and routes them to chief or worker agents.
    """

    agent_id = "orchestrator_agent"
    model = "claude-sonnet-4-6"

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        """Decompose task and coordinate dispatch to sub-agents."""
        # Stub: pass through to a worker
        return self._make_output(
            task=task,
            ctx=ctx,
            result=f"Orchestrating: {task.objective[:80]}...",
            status=OutputStatus.SUCCESS,
            data={"routed_sub_tasks": []},
            confidence=0.7,
        )
