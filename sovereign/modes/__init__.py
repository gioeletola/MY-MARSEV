"""Operating modes layer — 16 mode configurations."""
from sovereign.modes.base_mode import BaseMode
from sovereign.modes.builder_mode import BuilderMode
from sovereign.modes.business_mode import BusinessMode
from sovereign.modes.command_mode import CommandMode
from sovereign.modes.emergency_mode import EmergencyMode
from sovereign.modes.finance_mode import FinanceMode
from sovereign.modes.founder_mode import FounderMode
from sovereign.modes.local_offline_mode import Local_offlineMode
from sovereign.modes.personal_mode import PersonalMode
from sovereign.modes.prestige_mode import PrestigeMode
from sovereign.modes.recovery_mode import RecoveryMode
from sovereign.modes.research_mode import ResearchMode
from sovereign.modes.silent_mode import SilentMode
from sovereign.modes.study_mode import StudyMode
from sovereign.modes.survival_mode import SurvivalMode
from sovereign.modes.travel_mode import TravelMode
from sovereign.modes.war_mode import WarMode

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
    # Extended modes
    "founder":       FounderMode(),
    "war":           WarMode(),
    "prestige":      PrestigeMode(),
    "silent":        SilentMode(),
    "recovery":      RecoveryMode(),
    "emergency":     EmergencyMode(),
}

__all__ = [
    "BaseMode", "MODES",
    "BuilderMode", "BusinessMode", "CommandMode", "EmergencyMode",
    "FinanceMode", "FounderMode", "Local_offlineMode", "PersonalMode",
    "PrestigeMode", "RecoveryMode", "ResearchMode", "SilentMode",
    "StudyMode", "SurvivalMode", "TravelMode", "WarMode",
]
