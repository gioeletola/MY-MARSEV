"""Personal Research Center — personal research and intelligence gathering."""
from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

CENTER_ID = "personal_research_centre"
DESCRIPTION = "Personal Research & Intelligence"
PRIMARY_MODE = "personal"
AGENTS = ["knowledge_search", "knowledge_synthesis", "insight_agent", "reading_list", "personal_archivist"]

class PersonalResearchCenter:
    DOMAIN_MAP = {"search": "knowledge_search", "synthesis": "knowledge_synthesis", "insight": "insight_agent", "reading": "reading_list", "archive": "personal_archivist"}
    def route(self, objective: str) -> str:
        obj = objective.lower()
        for kw, aid in self.DOMAIN_MAP.items():
            if kw in obj:
                return aid
        return "knowledge_search"
    def describe(self) -> dict:
        return {"center_id": CENTER_ID, "description": DESCRIPTION, "agents": AGENTS}
center = PersonalResearchCenter()
