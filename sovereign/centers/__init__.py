"""
Operational Centers — SOVEREIGN AI OS.

Each center is a high-level coordination hub that aggregates related
domain agents and exposes a uniform route() / describe() interface.
Simple centers inherit from SimpleCenter; complex ones have async dispatch.
"""
from sovereign.centers.simple_center import SimpleCenter

# ── Simple centers (keyword routing only) ───────────────────────────────────
from sovereign.centers.ai_qa_center import AIQACenter
from sovereign.centers.automation_center import AutomationCenter
from sovereign.centers.concierge_center import ConciergeCenter
from sovereign.centers.cultural_center import CulturalCenter
from sovereign.centers.data_fabric_center import DataFabricCenter
from sovereign.centers.diary_center import DiaryCenter
from sovereign.centers.governance_center import GovernanceCenter
from sovereign.centers.inventory_center import InventoryCenter
from sovereign.centers.life_os_center import LifeOSCenter
from sovereign.centers.maximizer_center import MaximizerCenter
from sovereign.centers.media_editing_center import MediaEditingCenter
from sovereign.centers.partner_center import PartnerCenter
from sovereign.centers.personal_research_center import PersonalResearchCenter
from sovereign.centers.resilience_recovery_center import ResilienceRecoveryCenter
from sovereign.centers.scenario_simulation_center import ScenarioSimulationCenter
from sovereign.centers.second_brain_center import SecondBrainCenter
from sovereign.centers.vault_center import VaultCenter

# ── Full centers (async dispatch + agent registry) ──────────────────────────
from sovereign.centers.accounting_center import AccountingCenter
from sovereign.centers.bi_center import BusinessIntelligenceCenter
from sovereign.centers.business_center import BusinessCenter
from sovereign.centers.content_center import ContentCenter
from sovereign.centers.crm_center import CRMCenter
from sovereign.centers.hr_center import HRCenter
from sovereign.centers.legal_center import LegalCenter
from sovereign.centers.personal_center import PersonalCenter
from sovereign.centers.strategic_center import StrategicCenter

__all__ = [
    "SimpleCenter",
    # Simple
    "AIQACenter", "AutomationCenter", "ConciergeCenter", "CulturalCenter",
    "DataFabricCenter", "DiaryCenter", "GovernanceCenter", "InventoryCenter",
    "LifeOSCenter", "MaximizerCenter", "MediaEditingCenter", "PartnerCenter",
    "PersonalResearchCenter", "ResilienceRecoveryCenter", "ScenarioSimulationCenter",
    "SecondBrainCenter", "VaultCenter",
    # Full
    "AccountingCenter", "BusinessIntelligenceCenter", "BusinessCenter",
    "ContentCenter", "CRMCenter", "HRCenter", "LegalCenter",
    "PersonalCenter", "StrategicCenter",
]
