"""Second Brain Center — knowledge management and personal intelligence."""
from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

CENTER_ID = "second_brain_centre"
DESCRIPTION = "Second Brain & Knowledge Management"
PRIMARY_MODE = "personal"
AGENTS = ["second_brain_chief", "personal_archivist", "knowledge_organizer", "knowledge_search", "knowledge_synthesis", "insight_agent"]

class SecondBrainCenter:
    DOMAIN_MAP = {"knowledge": "knowledge_organizer", "search": "knowledge_search", "synthesis": "knowledge_synthesis", "insight": "insight_agent", "archive": "personal_archivist"}
    def route(self, objective: str) -> str:
        obj = objective.lower()
        for kw, aid in self.DOMAIN_MAP.items():
            if kw in obj:
                return aid
        return "second_brain_chief"
    def describe(self) -> dict:
        return {"center_id": CENTER_ID, "description": DESCRIPTION, "agents": AGENTS}
center = SecondBrainCenter()
