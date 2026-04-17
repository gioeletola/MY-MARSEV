"""Maximizer Center — personal performance and productivity maximization."""
from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

CENTER_ID = "maximizer_centre"
DESCRIPTION = "Personal Maximizer & Performance"
PRIMARY_MODE = "personal"
AGENTS = ["personal_maximizer_chief", "maximizer_agent", "productivity_auditor", "attention_auditor", "deep_work_scheduler"]

class MaximizerCenter:
    DOMAIN_MAP = {"productivity": "productivity_auditor", "attention": "attention_auditor", "deep work": "deep_work_scheduler", "maximiz": "maximizer_agent"}
    def route(self, objective: str) -> str:
        obj = objective.lower()
        for kw, aid in self.DOMAIN_MAP.items():
            if kw in obj:
                return aid
        return "personal_maximizer_chief"
    def describe(self) -> dict:
        return {"center_id": CENTER_ID, "description": DESCRIPTION, "agents": AGENTS}
center = MaximizerCenter()
