"""
Strategic Operational Center — coordinates black-tier and meta-level agents.
"""
from __future__ import annotations

import logging
from typing import Any

from sovereign.swarm.base_agent import AgentContext, AgentTask

logger = logging.getLogger(__name__)


class StrategicCenter:
    """
    Coordinates strategic / black-tier agents: Reality Twin, Time Machine,
    Attention Engine, Decision Intelligence, Opportunity Scanner,
    Networking, Resilience, Legacy, Exit planning.
    """

    DOMAIN_MAP: dict[str, str] = {
        "decision": "decision_intelligence_chief",
        "decide": "decision_intelligence_chief",
        "bias": "bias_detector",
        "attention": "attention_engine_chief",
        "focus": "attention_engine_chief",
        "distraction": "distraction_shield",
        "opportunity": "opportunity_scanner_chief",
        "opportunities": "opportunity_scanner_chief",
        "market": "market_intelligence",
        "trend": "market_intelligence",
        "network": "networking_strategist_chief",
        "networking": "networking_strategist_chief",
        "mentor": "mentor_finder",
        "legacy": "legacy_architect_chief",
        "impact": "impact_mapper",
        "exit": "sovereign_exit_chief",
        "estate": "estate_planning",
        "resilience": "resilience_chief",
        "risk": "spof_detector",
        "pattern": "pattern_detector",
        "scenario": "future_scenario",
        "future": "future_scenario",
        "trajectory": "trajectory_analyst",
        "twin": "reality_twin_chief",
        "alignment": "alignment_monitor",
        "audit": "sovereign_auditor",
        "privacy": "privacy_guardian",
        "security": "information_security",
    }

    def __init__(self, agent_registry: Any) -> None:
        self._registry = agent_registry

    def route(self, intent_keywords: list[str]) -> str:
        for kw in intent_keywords:
            if kw.lower() in self.DOMAIN_MAP:
                return self.DOMAIN_MAP[kw.lower()]
        return "decision_intelligence_chief"

    async def dispatch(
        self,
        task: AgentTask,
        ctx: AgentContext,
        intent_keywords: list[str] | None = None,
    ):
        agent_id = self.route(intent_keywords or [])
        agent = self._registry.get(agent_id)
        if agent is None:
            agent = self._registry.get("decision_intelligence_chief")
        if agent is None:
            raise RuntimeError("StrategicCenter: no agent available")
        logger.info("StrategicCenter routing to agent=%s", agent_id)
        return await agent.run(task, ctx)

    def list_domains(self) -> list[str]:
        return sorted(set(self.DOMAIN_MAP.values()))
