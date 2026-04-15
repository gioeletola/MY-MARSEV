"""
Business Operational Center — coordinates all business-domain agents.
"""
from __future__ import annotations
import logging
from typing import Any

from sovereign.swarm.base_agent import AgentContext, AgentTask

logger = logging.getLogger(__name__)


class BusinessCenter:
    """
    Coordinates business-domain chiefs: sales, marketing, ops, product,
    finance, legal, HR, and strategy sub-agents.

    Used by the orchestrator to route business requests to the right chief
    without having to know individual agent IDs.
    """

    DOMAIN_MAP: dict[str, str] = {
        "sales": "sales_chief",
        "revenue": "sales_chief",
        "crm": "sales_chief",
        "marketing": "marketing_chief",
        "brand": "marketing_chief",
        "content": "content_chief",
        "product": "product_chief",
        "roadmap": "product_chief",
        "operations": "ops_chief",
        "ops": "ops_chief",
        "process": "ops_chief",
        "finance": "finance_chief",
        "accounting": "finance_chief",
        "legal": "legal_chief",
        "compliance": "legal_chief",
        "hr": "hr_chief",
        "people": "hr_chief",
        "strategy": "strategy_chief",
        "competitive": "strategy_chief",
        "research": "research_chief",
        "analysis": "research_chief",
    }

    def __init__(self, agent_registry: Any) -> None:
        self._registry = agent_registry

    def route(self, intent_keywords: list[str]) -> str:
        """
        Given a list of intent keywords, return the most appropriate chief agent_id.
        Falls back to 'strategy_chief' if no match.
        """
        for kw in intent_keywords:
            kw_lower = kw.lower()
            if kw_lower in self.DOMAIN_MAP:
                return self.DOMAIN_MAP[kw_lower]
        return "strategy_chief"

    async def dispatch(
        self,
        task: AgentTask,
        ctx: AgentContext,
        intent_keywords: list[str] | None = None,
    ):
        """Route and execute a task through the appropriate business chief."""
        agent_id = self.route(intent_keywords or [])
        agent = self._registry.get(agent_id)
        if agent is None:
            logger.warning("BusinessCenter: no agent found for id=%s", agent_id)
            # fallback to any strategy chief
            agent = self._registry.get("strategy_chief")
        if agent is None:
            raise RuntimeError(f"BusinessCenter: no fallback agent available")
        logger.info("BusinessCenter routing to agent=%s", agent_id)
        return await agent.run(task, ctx)

    def list_domains(self) -> list[str]:
        return sorted(set(self.DOMAIN_MAP.values()))
