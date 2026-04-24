"""
Provisioning planner — maps a BusinessProfile to a ProvisioningPlan,
deciding which centers, agents, vaults, and connectors to activate.
"""
from __future__ import annotations

from sovereign.provisioning.types import BusinessProfile, BusinessTier, ProvisioningPlan

# Centers always enabled regardless of tier
_CORE_CENTERS = [
    "business_center", "concierge_center", "vault_center", "governance_center",
]

_TIER_CENTERS: dict[BusinessTier, list[str]] = {
    BusinessTier.SOLO: [
        "personal_center", "diary_center", "second_brain_center",
        "personal_research_center",
    ],
    BusinessTier.STARTUP: [
        "crm_center", "accounting_center", "content_center",
        "hr_center", "legal_center", "automation_center",
    ],
    BusinessTier.SCALE: [
        "bi_center", "data_fabric_center", "strategic_center",
        "partner_center", "inventory_center", "ai_qa_center",
        "maximizer_center", "cultural_center",
    ],
    BusinessTier.ENTERPRISE: [
        "scenario_simulation_center", "resilience_recovery_center",
        "media_editing_center", "life_os_center",
    ],
}

_CORE_AGENTS = [
    "ceo_agent", "chief_of_staff", "guardian", "coordinator",
]

_TIER_AGENTS: dict[BusinessTier, list[str]] = {
    BusinessTier.SOLO: ["task_manager", "knowledge_curator", "daily_digest"],
    BusinessTier.STARTUP: [
        "sales_agent", "content_writer", "finance_analyst",
        "legal_advisor", "hr_specialist",
    ],
    BusinessTier.SCALE: [
        "market_analyst", "data_scientist", "seo_specialist",
        "risk_analyst", "growth_hacker",
    ],
    BusinessTier.ENTERPRISE: [
        "enterprise_strategist", "m_and_a_advisor", "crisis_manager",
    ],
}

_CORE_VAULTS = ["main", "secrets", "documents"]

_TIER_VAULTS: dict[BusinessTier, list[str]] = {
    BusinessTier.STARTUP: ["financials", "legal"],
    BusinessTier.SCALE: ["analytics", "hr", "crm"],
    BusinessTier.ENTERPRISE: ["compliance", "m_and_a"],
}

_TIER_SKILLS: dict[BusinessTier, list[str]] = {
    BusinessTier.SOLO: ["daily-digest", "email-draft", "meeting-notes"],
    BusinessTier.STARTUP: ["web-summarize", "knowledge-extract", "calendar-prep"],
    BusinessTier.SCALE: ["topic-research", "file-organizer", "dependency-audit"],
    BusinessTier.ENTERPRISE: [],
}


def build_plan(profile: BusinessProfile) -> ProvisioningPlan:
    tier = profile.tier
    tiers = [BusinessTier.SOLO, BusinessTier.STARTUP, BusinessTier.SCALE, BusinessTier.ENTERPRISE]
    tier_idx = tiers.index(tier) if tier in tiers else 0

    centers = list(_CORE_CENTERS)
    agents = list(_CORE_AGENTS)
    vaults = list(_CORE_VAULTS)
    skills: list[str] = []

    for i, t in enumerate(tiers):
        if i <= tier_idx:
            centers.extend(_TIER_CENTERS.get(t, []))
            agents.extend(_TIER_AGENTS.get(t, []))
            vaults.extend(_TIER_VAULTS.get(t, []))
            skills.extend(_TIER_SKILLS.get(t, []))

    return ProvisioningPlan(
        business_id=f"biz_{profile.name.lower().replace(' ', '_')}",
        profile=profile,
        centers_to_bind=centers,
        agents_to_bind=agents,
        vaults_to_create=vaults,
        skills_to_enable=skills,
    )
