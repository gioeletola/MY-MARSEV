"""
Business Intelligence Center — analytics, KPIs, forecasting, and market intelligence.
"""
from __future__ import annotations

import logging
from typing import Any

from sovereign.swarm.base_agent import AgentContext, AgentTask

logger = logging.getLogger(__name__)

CENTER_ID = "bi_centre"
DESCRIPTION = "Business Intelligence & Analytics"
PRIMARY_MODE = "business"
AGENTS = [
    "bi_chief",
    "kpi_architect",
    "forecasting_agent",
    "opportunity_scanner",
    "competitor_watch",
    "scenario_simulator",
]


class BusinessIntelligenceCenter:
    """
    Coordinates business intelligence agents: KPI tracking, forecasting,
    opportunity scanning, competitor analysis, and scenario simulation.

    Used by the orchestrator to route analytics and intelligence requests
    to the appropriate BI agent without knowing individual IDs.
    """

    DOMAIN_MAP: dict[str, str] = {
        "intelligence": "bi_chief",
        "analytics": "bi_chief",
        "bi": "bi_chief",
        "kpi": "kpi_architect",
        "metric": "kpi_architect",
        "metrics": "kpi_architect",
        "dashboard": "kpi_architect",
        "forecast": "forecasting_agent",
        "forecasting": "forecasting_agent",
        "prediction": "forecasting_agent",
        "opportunity": "opportunity_scanner",
        "opportunities": "opportunity_scanner",
        "competitor": "competitor_watch",
        "competition": "competitor_watch",
        "competitive": "competitor_watch",
        "scenario": "scenario_simulator",
        "simulation": "scenario_simulator",
        "simulate": "scenario_simulator",
    }

    def __init__(self, agent_registry: Any) -> None:
        self._registry = agent_registry

    def route(self, intent_keywords: list[str]) -> str:
        """Return the most appropriate BI agent_id for the given intent keywords."""
        for kw in intent_keywords:
            if kw.lower() in self.DOMAIN_MAP:
                return self.DOMAIN_MAP[kw.lower()]
        return "bi_chief"

    async def dispatch(
        self,
        task: AgentTask,
        ctx: AgentContext,
        intent_keywords: list[str] | None = None,
    ):
        """Route and execute a task through the appropriate BI agent."""
        agent_id = self.route(intent_keywords or [])
        agent = self._registry.get(agent_id)
        if agent is None:
            logger.warning("BusinessIntelligenceCenter: no agent found for id=%s", agent_id)
            agent = self._registry.get("bi_chief")
        if agent is None:
            raise RuntimeError("BusinessIntelligenceCenter: no agent available")
        logger.info("BusinessIntelligenceCenter routing to agent=%s", agent_id)
        return await agent.run(task, ctx)

    def list_domains(self) -> list[str]:
        return sorted(set(self.DOMAIN_MAP.values()))
