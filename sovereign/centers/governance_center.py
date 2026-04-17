"""Governance Center — system governance and policy."""
from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

CENTER_ID = "governance_centre"
DESCRIPTION = "System Governance & Policy"
PRIMARY_MODE = "command"
AGENTS = ["sovereign_auditor", "permission_auditor", "compliance_agent"]
REQUIRES_REVIEW = True

class GovernanceCenter:
    DOMAIN_MAP = {"audit": "sovereign_auditor", "permission": "permission_auditor", "compliance": "compliance_agent", "governance": "sovereign_auditor", "policy": "sovereign_auditor"}
    def route(self, objective: str) -> str:
        obj = objective.lower()
        for kw, aid in self.DOMAIN_MAP.items():
            if kw in obj:
                return aid
        return "sovereign_auditor"
    def describe(self) -> dict:
        return {"center_id": CENTER_ID, "description": DESCRIPTION, "agents": AGENTS, "requires_review": REQUIRES_REVIEW}
center = GovernanceCenter()
