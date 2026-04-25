"""
Legal Center — legal review, contract tracking, compliance, and documentation.
"""
from __future__ import annotations

import logging
from typing import Any

from sovereign.swarm.base_agent import AgentContext, AgentTask

logger = logging.getLogger(__name__)

CENTER_ID = "legal_centre"
DESCRIPTION = "Legal & Compliance"
REQUIRES_REVIEW = True
AGENTS = [
    "legal_review",
    "contract_tracker",
    "compliance_agent",
    "deadline_monitor",
    "documentation_agent",
]


class LegalCenter:
    """
    Coordinates legal and compliance agents: contract review, compliance checks,
    deadline monitoring, and legal documentation.

    Requires human review before any outputs are acted upon.
    Used by the orchestrator to route legal and compliance requests to the
    appropriate agent without knowing individual IDs.
    """

    DOMAIN_MAP: dict[str, str] = {
        "legal": "legal_review",
        "review": "legal_review",
        "contract": "contract_tracker",
        "contracts": "contract_tracker",
        "agreement": "contract_tracker",
        "compliance": "compliance_agent",
        "regulation": "compliance_agent",
        "regulatory": "compliance_agent",
        "deadline": "deadline_monitor",
        "deadlines": "deadline_monitor",
        "expiry": "deadline_monitor",
        "documentation": "documentation_agent",
        "document": "documentation_agent",
        "filing": "documentation_agent",
    }

    def __init__(self, agent_registry: Any) -> None:
        self._registry = agent_registry

    def route(self, intent_keywords: list[str]) -> str:
        """Return the most appropriate legal agent_id for the given intent keywords."""
        for kw in intent_keywords:
            if kw.lower() in self.DOMAIN_MAP:
                return self.DOMAIN_MAP[kw.lower()]
        return "legal_review"

    async def dispatch(
        self,
        task: AgentTask,
        ctx: AgentContext,
        intent_keywords: list[str] | None = None,
    ):
        """Route and execute a task through the appropriate legal agent."""
        agent_id = self.route(intent_keywords or [])
        agent = self._registry.get(agent_id)
        if agent is None:
            logger.warning("LegalCenter: no agent found for id=%s", agent_id)
            agent = self._registry.get("legal_review")
        if agent is None:
            raise RuntimeError("LegalCenter: no agent available")
        logger.info("LegalCenter routing to agent=%s (requires_review=True)", agent_id)
        return await agent.run(task, ctx)

    def list_domains(self) -> list[str]:
        return sorted(set(self.DOMAIN_MAP.values()))
