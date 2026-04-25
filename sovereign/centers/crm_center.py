"""
CRM Center — sales operations, lead management, and client relationships.
"""
from __future__ import annotations

import logging
from typing import Any

from sovereign.swarm.base_agent import AgentContext, AgentTask

logger = logging.getLogger(__name__)

CENTER_ID = "crm_centre"
DESCRIPTION = "CRM & Sales Operations"
AGENTS = [
    "crm_chief",
    "lead_hunter",
    "lead_scoring",
    "follow_up_agent",
    "proposal_agent",
    "client_memory",
    "retention_agent",
    "pipeline_cleaner",
    "client_reactivation",
    "meeting_prep",
]


class CRMCenter:
    """
    Coordinates CRM and sales operations agents: lead generation, scoring,
    follow-ups, proposals, client retention, pipeline hygiene, and meeting prep.

    Used by the orchestrator to route sales and CRM requests to the
    appropriate agent without knowing individual IDs.
    """

    DOMAIN_MAP: dict[str, str] = {
        "crm": "crm_chief",
        "sales": "crm_chief",
        "lead": "lead_hunter",
        "leads": "lead_hunter",
        "prospecting": "lead_hunter",
        "scoring": "lead_scoring",
        "lead_score": "lead_scoring",
        "follow_up": "follow_up_agent",
        "followup": "follow_up_agent",
        "follow": "follow_up_agent",
        "proposal": "proposal_agent",
        "proposals": "proposal_agent",
        "quote": "proposal_agent",
        "client": "client_memory",
        "memory": "client_memory",
        "retention": "retention_agent",
        "churn": "retention_agent",
        "pipeline": "pipeline_cleaner",
        "reactivation": "client_reactivation",
        "reactivate": "client_reactivation",
        "meeting": "meeting_prep",
        "prep": "meeting_prep",
    }

    def __init__(self, agent_registry: Any) -> None:
        self._registry = agent_registry

    def route(self, intent_keywords: list[str]) -> str:
        """Return the most appropriate CRM agent_id for the given intent keywords."""
        for kw in intent_keywords:
            if kw.lower() in self.DOMAIN_MAP:
                return self.DOMAIN_MAP[kw.lower()]
        return "crm_chief"

    async def dispatch(
        self,
        task: AgentTask,
        ctx: AgentContext,
        intent_keywords: list[str] | None = None,
    ):
        """Route and execute a task through the appropriate CRM agent."""
        agent_id = self.route(intent_keywords or [])
        agent = self._registry.get(agent_id)
        if agent is None:
            logger.warning("CRMCenter: no agent found for id=%s", agent_id)
            agent = self._registry.get("crm_chief")
        if agent is None:
            raise RuntimeError("CRMCenter: no agent available")
        logger.info("CRMCenter routing to agent=%s", agent_id)
        return await agent.run(task, ctx)

    def list_domains(self) -> list[str]:
        return sorted(set(self.DOMAIN_MAP.values()))
