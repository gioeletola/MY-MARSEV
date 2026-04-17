"""Life OS Center — life operating system and daily management."""
from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

CENTER_ID = "life_os_centre"
DESCRIPTION = "Life Operating System"
PRIMARY_MODE = "personal"
AGENTS = ["life_os_chief", "life_admin", "routine_agent", "energy_manager", "habit_engineer", "reminder_intelligence", "smart_calendar", "smart_alarm", "errand_coordinator", "admin_cleaner", "renewal_agent", "subscription_manager"]

class LifeOSCenter:
    DOMAIN_MAP = {"habit": "habit_engineer", "routine": "routine_agent", "calendar": "smart_calendar", "reminder": "reminder_intelligence", "energy": "energy_manager", "subscription": "subscription_manager", "errand": "errand_coordinator", "admin": "admin_cleaner"}
    def route(self, objective: str) -> str:
        obj = objective.lower()
        for kw, aid in self.DOMAIN_MAP.items():
            if kw in obj:
                return aid
        return "life_os_chief"
    def describe(self) -> dict:
        return {"center_id": CENTER_ID, "description": DESCRIPTION, "agents": AGENTS}
center = LifeOSCenter()
