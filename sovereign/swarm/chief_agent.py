"""Chief Agent — domain-owning agent that supervises workers in its domain."""
from __future__ import annotations

from sovereign.output.output_contract import OutputStatus, StructuredOutput
from sovereign.swarm.base_agent import AgentContext, AgentTask, BaseAgent


class ChiefAgent(BaseAgent):
    """
    Domain chief. Owns a specific domain (e.g. research, finance, content),
    supervises domain workers, and consolidates their outputs.

    Subclass this for domain-specific chiefs (ResearchChief, FinanceChief, etc.).
    """

    agent_id = "chief"
    model = "claude-sonnet-4-6"
    domain: str = "general"

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        return self._make_output(
            task=task,
            ctx=ctx,
            result=f"[{self.domain.upper()} CHIEF] {task.objective[:100]}",
            status=OutputStatus.SUCCESS,
            confidence=0.75,
        )
