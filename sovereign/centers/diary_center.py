"""Diary Center — diary, reflection, and journaling."""
from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

CENTER_ID = "diary_centre"
DESCRIPTION = "Diary & Reflection"
PRIMARY_MODE = "personal"
AGENTS = ["diary_chief", "daily_reflection", "mood_pattern", "weekly_review", "sunday_reset", "impulse_filter"]

class DiaryCenter:
    DOMAIN_MAP = {"diary": "diary_chief", "reflect": "daily_reflection", "mood": "mood_pattern", "weekly": "weekly_review", "sunday": "sunday_reset", "impulse": "impulse_filter"}
    def route(self, objective: str) -> str:
        obj = objective.lower()
        for kw, aid in self.DOMAIN_MAP.items():
            if kw in obj:
                return aid
        return "diary_chief"
    def describe(self) -> dict:
        return {"center_id": CENTER_ID, "description": DESCRIPTION, "agents": AGENTS}
center = DiaryCenter()
