"""
Ephemeral Agent — short-lived, single-objective sub-agent.

Spawned by the AgentFactory for one narrow task. Auto-terminates on
task completion, stop condition, or TTL expiry.
"""
from __future__ import annotations

import logging
import time

from sovereign.swarm.base_agent import AgentContext, AgentTask, BaseAgent
from sovereign.output.output_contract import OutputStatus, StructuredOutput

logger = logging.getLogger(__name__)


class EphemeralAgent(BaseAgent):
    """
    An ephemeral sub-agent with a single objective and TTL.

    Created by AgentFactory.spawn(spec). Receives its objective from
    the AgentSpec; results are saved to memory before the agent is
    garbage-collected by AgentFactory.despawn().
    """

    agent_id = "ephemeral"
    model = "claude-haiku-4-5-20251001"

    def __init__(self, spec: "AgentSpec", *args, **kwargs) -> None:  # type: ignore[name-defined]
        super().__init__(*args, **kwargs)
        self.spec = spec
        self.agent_id = f"ephemeral_{spec.name}"
        self.model = spec.model
        self._spawned_at = time.monotonic()

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        """Execute the spec's objective within scope and TTL constraints."""
        # Check TTL
        elapsed = time.monotonic() - self._spawned_at
        if elapsed > self.spec.ttl_seconds:
            return StructuredOutput.failure(
                session_id=ctx.session_id,
                agent_id=self.agent_id,
                task_id=task.task_id,
                error=f"TTL expired ({elapsed:.0f}s > {self.spec.ttl_seconds}s)",
            )

        try:
            result_text = await self._call_claude(
                messages=[{"role": "user", "content": task.objective}],
                ctx=ctx,
                task=task,
                max_tokens=2048,
            )
            return self._make_output(
                task=task,
                ctx=ctx,
                result=result_text,
                status=OutputStatus.SUCCESS,
                confidence=0.7,
            )
        except Exception as exc:
            logger.error("EphemeralAgent failed", agent=self.agent_id, error=str(exc))
            return StructuredOutput.failure(
                session_id=ctx.session_id,
                agent_id=self.agent_id,
                task_id=task.task_id,
                error=str(exc),
            )

    def _is_within_scope(self, action: str) -> bool:
        """Check whether an action is within the spec's scope constraints."""
        blocked = self.spec.scope.get("blocked_actions", [])
        return action not in blocked
