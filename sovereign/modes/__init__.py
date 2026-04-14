"""Operating modes layer — all 10 mode configurations."""
from sovereign.modes.base_mode import BaseMode
from sovereign.modes.builder_mode import BuilderMode
from sovereign.modes.business_mode import BusinessMode
from sovereign.modes.command_mode import CommandMode
from sovereign.modes.finance_mode import FinanceMode
from sovereign.modes.local_offline_mode import Local_offlineMode
from sovereign.modes.personal_mode import PersonalMode
from sovereign.modes.research_mode import ResearchMode
from sovereign.modes.study_mode import StudyMode
from sovereign.modes.survival_mode import SurvivalMode
from sovereign.modes.travel_mode import TravelMode

# Registry of all available modes — keyed by mode name
MODES: dict[str, BaseMode] = {
    "command":       CommandMode(),
    "business":      BusinessMode(),
    "personal":      PersonalMode(),
    "finance":       FinanceMode(),
    "study":         StudyMode(),
    "travel":        TravelMode(),
    "research":      ResearchMode(),
    "builder":       BuilderMode(),
    "local_offline": Local_offlineMode(),
    "survival":      SurvivalMode(),
}

__all__ = [
    "BaseMode",
    "MODES",
    "BuilderMode",
    "BusinessMode",
    "CommandMode",
    "FinanceMode",
    "Local_offlineMode",
    "PersonalMode",
    "ResearchMode",
    "StudyMode",
    "SurvivalMode",
    "TravelMode",
]
