"""Orchestrator Agent — routes work, breaks it into sub-problems, coordinates execution."""
from __future__ import annotations

from sovereign.output.output_contract import OutputStatus, StructuredOutput
from sovereign.swarm.base_agent import AgentContext, AgentTask, BaseAgent


class OrchestratorAgent(BaseAgent):
    """
    Mid-tier orchestration agent. Receives complex tasks from the executive layer
    and further decomposes and routes them to chief or worker agents.
    """

    agent_id = "orchestrator_agent"
    model = "claude-sonnet-4-6"

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        """Decompose task and coordinate dispatch to sub-agents."""
        result, _ = await self._call_with_tools(
            messages=[{"role": "user", "content": (
                f"You are the Orchestrator Agent of the SOVEREIGN AI OS.\n"
                f"Decompose the following task into clear sub-tasks and describe "
                f"how each sub-task should be routed to specialized agents.\n\n"
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
            data={"routed_sub_tasks": []},
            confidence=0.75,
        )
