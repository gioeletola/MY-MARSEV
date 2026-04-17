"""
HR Center — recruiting, talent management, onboarding, and organizational design.
"""
from __future__ import annotations
import logging
from typing import Any

from sovereign.swarm.base_agent import AgentContext, AgentTask

logger = logging.getLogger(__name__)

CENTER_ID = "hr_centre"
DESCRIPTION = "HR & Recruiting Operations"
AGENTS = [
    "hr_chief",
    "recruiter_agent",
    "cv_screening",
    "talent_ranking",
    "onboarding_agent",
    "team_performance",
    "org_design",
]


class HRCenter:
    """
    Coordinates HR and recruiting agents: talent acquisition, CV screening,
    candidate ranking, onboarding, team performance tracking, and org design.

    Used by the orchestrator to route HR and people-ops requests to the
    appropriate agent without knowing individual IDs.
    """

    DOMAIN_MAP: dict[str, str] = {
        "hr": "hr_chief",
        "people": "hr_chief",
        "human_resources": "hr_chief",
        "recruiting": "recruiter_agent",
        "recruitment": "recruiter_agent",
        "hire": "recruiter_agent",
        "hiring": "recruiter_agent",
        "cv": "cv_screening",
        "resume": "cv_screening",
        "screening": "cv_screening",
        "candidate": "talent_ranking",
        "ranking": "talent_ranking",
        "talent": "talent_ranking",
        "onboarding": "onboarding_agent",
        "onboard": "onboarding_agent",
        "performance": "team_performance",
        "team": "team_performance",
        "org": "org_design",
        "organization": "org_design",
        "structure": "org_design",
    }

    def __init__(self, agent_registry: Any) -> None:
        self._registry = agent_registry

    def route(self, intent_keywords: list[str]) -> str:
        """Return the most appropriate HR agent_id for the given intent keywords."""
        for kw in intent_keywords:
            if kw.lower() in self.DOMAIN_MAP:
                return self.DOMAIN_MAP[kw.lower()]
        return "hr_chief"

    async def dispatch(
        self,
        task: AgentTask,
        ctx: AgentContext,
        intent_keywords: list[str] | None = None,
    ):
        """Route and execute a task through the appropriate HR agent."""
        agent_id = self.route(intent_keywords or [])
        agent = self._registry.get(agent_id)
        if agent is None:
            logger.warning("HRCenter: no agent found for id=%s", agent_id)
            agent = self._registry.get("hr_chief")
        if agent is None:
            raise RuntimeError("HRCenter: no agent available")
        logger.info("HRCenter routing to agent=%s", agent_id)
        return await agent.run(task, ctx)

    def list_domains(self) -> list[str]:
        return sorted(set(self.DOMAIN_MAP.values()))
