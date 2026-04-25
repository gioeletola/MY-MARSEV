"""Labs Framework for SOVEREIGN AI OS — 21 experimental research labs."""
# pylint: disable=import-error  (3d_lab has a numeric prefix — valid module)
from sovereign.labs.ai_experiment_lab import AIExperimentLab
from sovereign.labs.automation_lab import AutomationLab
from sovereign.labs.behavioral_lab import BehavioralLab
from sovereign.labs.bio_lab import BioLab
from sovereign.labs.black_swan_lab import BlackSwanLab
from sovereign.labs.cyber_lab import CyberLab
from sovereign.labs.decision_science_lab import DecisionScienceLab
from sovereign.labs.design_lab import DesignLab
from sovereign.labs.finance_lab import FinanceLab
from sovereign.labs.future_systems_lab import FutureSystemsLab
from sovereign.labs.georisk_lab import GeoRiskLab
from sovereign.labs.labs_framework import LabsFramework
from sovereign.labs.media_lab import MediaLab
from sovereign.labs.memory_lab import MemoryLab
from sovereign.labs.offline_survival_lab import OfflineSurvivalLab
from sovereign.labs.product_lab import ProductLab
from sovereign.labs.red_team_lab import RedTeamLab
from sovereign.labs.research_lab import ResearchLab
from sovereign.labs.simulation_lab import SimulationLab
from sovereign.labs.social_dynamics_lab import SocialDynamicsLab
from sovereign.labs.strategy_lab import StrategyLab

__all__ = [
    "LabsFramework",
    "AIExperimentLab", "AutomationLab", "BehavioralLab", "BioLab",
    "BlackSwanLab", "CyberLab", "DecisionScienceLab", "DesignLab",
    "FinanceLab", "FutureSystemsLab", "GeoRiskLab", "MediaLab",
    "MemoryLab", "OfflineSurvivalLab", "ProductLab", "RedTeamLab",
    "ResearchLab", "SimulationLab", "SocialDynamicsLab", "StrategyLab",
]
