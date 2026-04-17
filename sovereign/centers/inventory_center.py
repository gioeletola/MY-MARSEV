"""Inventory Center — personal inventory and asset management."""
from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

CENTER_ID = "inventory_centre"
DESCRIPTION = "Personal Inventory Management"
PRIMARY_MODE = "personal"
AGENTS = ["inventory_chief", "personal_inventory_custodian", "dead_weight", "possession_rotation"]

class InventoryCenter:
    DOMAIN_MAP = {"inventory": "inventory_chief", "possession": "personal_inventory_custodian", "dead weight": "dead_weight", "rotation": "possession_rotation"}
    def route(self, objective: str) -> str:
        obj = objective.lower()
        for kw, aid in self.DOMAIN_MAP.items():
            if kw in obj:
                return aid
        return "inventory_chief"
    def describe(self) -> dict:
        return {"center_id": CENTER_ID, "description": DESCRIPTION, "agents": AGENTS}
center = InventoryCenter()
