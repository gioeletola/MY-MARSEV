"""Media Editing Center — media production and publishing."""
from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

CENTER_ID = "media_editing_centre"
DESCRIPTION = "Media Editing & Publishing"
PRIMARY_MODE = "business"
AGENTS = ["media_chief", "content_production", "publishing_queue", "thumbnail_brief", "clip_finder"]

class MediaEditingCenter:
    DOMAIN_MAP = {"media": "media_chief", "publish": "publishing_queue", "thumbnail": "thumbnail_brief", "clip": "clip_finder", "content": "content_production"}
    def route(self, objective: str) -> str:
        obj = objective.lower()
        for kw, aid in self.DOMAIN_MAP.items():
            if kw in obj:
                return aid
        return "media_chief"
    def describe(self) -> dict:
        return {"center_id": CENTER_ID, "description": DESCRIPTION, "agents": AGENTS}
center = MediaEditingCenter()
