"""Concierge Center — personal concierge and logistics."""
from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

CENTER_ID = "concierge_centre"
DESCRIPTION = "Personal Concierge & Logistics"
PRIMARY_MODE = "personal"
AGENTS = ["concierge_chief", "travel_planner", "event_prep", "home_asset_assistant", "emergency_contact"]

class ConciergeCenter:
    DOMAIN_MAP = {"travel": "travel_planner", "event": "event_prep", "home": "home_asset_assistant", "emergency": "emergency_contact"}
    def route(self, objective: str) -> str:
        obj = objective.lower()
        for kw, aid in self.DOMAIN_MAP.items():
            if kw in obj:
                return aid
        return "concierge_chief"
    def describe(self) -> dict:
        return {"center_id": CENTER_ID, "description": DESCRIPTION, "agents": AGENTS}
center = ConciergeCenter()
