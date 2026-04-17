"""
Content Center — content production, media publishing, and performance optimization.
"""
from __future__ import annotations
import logging
from typing import Any

from sovereign.swarm.base_agent import AgentContext, AgentTask

logger = logging.getLogger(__name__)

CENTER_ID = "content_centre"
DESCRIPTION = "Content Production & Media"
AGENTS = [
    "media_chief",
    "content_production",
    "clip_finder",
    "publishing_queue",
    "thumbnail_brief",
    "content_recycling",
    "performance_optimizer",
]


class ContentCenter:
    """
    Coordinates content production and media agents: content creation,
    clip finding, publishing scheduling, thumbnail briefs, content recycling,
    and performance optimization.

    Used by the orchestrator to route content and media requests to the
    appropriate agent without knowing individual IDs.
    """

    DOMAIN_MAP: dict[str, str] = {
        "content": "media_chief",
        "media": "media_chief",
        "production": "content_production",
        "create": "content_production",
        "writing": "content_production",
        "clip": "clip_finder",
        "clips": "clip_finder",
        "video": "clip_finder",
        "publish": "publishing_queue",
        "publishing": "publishing_queue",
        "schedule": "publishing_queue",
        "thumbnail": "thumbnail_brief",
        "thumbnails": "thumbnail_brief",
        "recycle": "content_recycling",
        "repurpose": "content_recycling",
        "recycling": "content_recycling",
        "performance": "performance_optimizer",
        "optimize": "performance_optimizer",
        "optimization": "performance_optimizer",
    }

    def __init__(self, agent_registry: Any) -> None:
        self._registry = agent_registry

    def route(self, intent_keywords: list[str]) -> str:
        """Return the most appropriate content agent_id for the given intent keywords."""
        for kw in intent_keywords:
            if kw.lower() in self.DOMAIN_MAP:
                return self.DOMAIN_MAP[kw.lower()]
        return "media_chief"

    async def dispatch(
        self,
        task: AgentTask,
        ctx: AgentContext,
        intent_keywords: list[str] | None = None,
    ):
        """Route and execute a task through the appropriate content agent."""
        agent_id = self.route(intent_keywords or [])
        agent = self._registry.get(agent_id)
        if agent is None:
            logger.warning("ContentCenter: no agent found for id=%s", agent_id)
            agent = self._registry.get("media_chief")
        if agent is None:
            raise RuntimeError("ContentCenter: no agent available")
        logger.info("ContentCenter routing to agent=%s", agent_id)
        return await agent.run(task, ctx)

    def list_domains(self) -> list[str]:
        return sorted(set(self.DOMAIN_MAP.values()))
