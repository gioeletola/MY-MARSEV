"""
Self-healer — responds to degraded health states with corrective actions.

In the current stub, corrective actions are logged recommendations.
Wire up to real remediation actions (despawn agents, reset clients, etc.)
for production use.
"""
from __future__ import annotations

import logging

from sovereign.observability.health_monitor import HealthStatus

logger = logging.getLogger(__name__)


class SelfHealer:
    """
    Evaluates a HealthStatus and applies or recommends corrective actions.

    Corrective strategies (stub):
    - degraded token_budget → reduce max_tokens per call
    - degraded error_rate   → switch to a cheaper/more stable model
    - high ephemeral count  → despawn idle agents
    """

    def evaluate(self, status: HealthStatus) -> list[str]:
        """
        Return a list of recommended or applied corrective actions.
        """
        actions: list[str] = []

        if status.checks.get("token_budget") == "degraded":
            actions.append("Reduce max_tokens per call to conserve budget.")
            logger.warning("Self-healer: token budget degraded — reducing max_tokens.")

        if status.checks.get("error_rate") == "degraded":
            actions.append("Switch to balanced model tier to reduce error rate.")
            logger.warning("Self-healer: high error rate — recommending model downgrade.")

        if status.checks.get("ephemeral_agents") == "degraded":
            actions.append("Despawn idle ephemeral agents to free concurrency slots.")
            logger.warning("Self-healer: high ephemeral agent count.")

        if status.overall == "critical":
            actions.append("CRITICAL: Escalate to human authority immediately.")
            logger.error("Self-healer: CRITICAL system state detected.")

        return actions
