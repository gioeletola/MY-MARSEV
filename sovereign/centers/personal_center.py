"""
Personal Operational Center — coordinates all personal-domain agents.
"""
from __future__ import annotations

import logging
from typing import Any

from sovereign.swarm.base_agent import AgentContext, AgentTask

logger = logging.getLogger(__name__)


class PersonalCenter:
    """
    Coordinates personal-domain chiefs: Life OS, Second Brain, TigerFlow,
    Social, Inventory, Maximizer, Concierge, Cultural, and Diary agents.
    """

    DOMAIN_MAP: dict[str, str] = {
        "goal": "goal_architect",
        "goals": "goal_architect",
        "habit": "habit_engineer",
        "habits": "habit_engineer",
        "identity": "identity_architect",
        "energy": "energy_manager",
        "health": "health_tracker",
        "relationship": "relationship_manager",
        "relationships": "relationship_manager",
        "knowledge": "knowledge_capture",
        "note": "knowledge_capture",
        "learn": "learning_path",
        "learning": "learning_path",
        "study": "learning_path",
        "task": "task_prioritizer",
        "tasks": "task_prioritizer",
        "productivity": "tiger_flow_chief",
        "focus": "focus_optimizer",
        "calendar": "calendar_manager",
        "schedule": "calendar_manager",
        "travel": "travel_planner",
        "trip": "travel_planner",
        "social": "social_intelligence_chief",
        "network": "network_mapper",
        "reflect": "daily_reflection",
        "reflection": "daily_reflection",
        "journal": "diary_chief",
        "review": "weekly_review",
        "subscription": "subscription_manager",
        "inventory": "inventory_chief",
        "culture": "cultural_intelligence_chief",
        "language": "language_assistant",
    }

    def __init__(self, agent_registry: Any) -> None:
        self._registry = agent_registry

    def route(self, intent_keywords: list[str]) -> str:
        for kw in intent_keywords:
            if kw.lower() in self.DOMAIN_MAP:
                return self.DOMAIN_MAP[kw.lower()]
        return "life_os_chief"

    async def dispatch(
        self,
        task: AgentTask,
        ctx: AgentContext,
        intent_keywords: list[str] | None = None,
    ):
        agent_id = self.route(intent_keywords or [])
        agent = self._registry.get(agent_id)
        if agent is None:
            agent = self._registry.get("life_os_chief")
        if agent is None:
            raise RuntimeError("PersonalCenter: no agent available")
        logger.info("PersonalCenter routing to agent=%s", agent_id)
        return await agent.run(task, ctx)

    def list_domains(self) -> list[str]:
        return sorted(set(self.DOMAIN_MAP.values()))
