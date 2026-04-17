"""Vault Center — personal document security and backup."""
from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

CENTER_ID = "vault_centre"
DESCRIPTION = "Personal Vault & Document Security"
PRIMARY_MODE = "personal"
AGENTS = ["document_manager", "document_readiness", "backup_integrity"]
REQUIRES_REVIEW = True

class VaultCenter:
    DOMAIN_MAP = {"document": "document_manager", "doc": "document_manager", "backup": "backup_integrity", "readiness": "document_readiness"}
    def route(self, objective: str) -> str:
        obj = objective.lower()
        for kw, aid in self.DOMAIN_MAP.items():
            if kw in obj:
                return aid
        return "document_manager"
    def describe(self) -> dict:
        return {"center_id": CENTER_ID, "description": DESCRIPTION, "agents": AGENTS, "requires_review": REQUIRES_REVIEW}
center = VaultCenter()
