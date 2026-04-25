"""Memory domain modules — typed record schemas for all 18 memory domains."""
from sovereign.memory.domains.brand import BrandAsset, BrandIdentity, BrandMemoryStore
from sovereign.memory.domains.business_idea import BusinessIdea, BusinessIdeaMemoryStore
from sovereign.memory.domains.next_action import NextAction, NextActionStore
from sovereign.memory.domains.personal_constitution import (
    PersonalConstitutionStore,
    RedFlag,
)
from sovereign.memory.domains.personal_version import PersonalVersion, PersonalVersionStore
from sovereign.memory.domains.content import ContentCalendarEntry, ContentMemoryStore, ContentPiece
from sovereign.memory.domains.decision import DecisionMemoryStore, DecisionRecord
from sovereign.memory.domains.diary import DiaryEntry, DiaryMemoryStore
from sovereign.memory.domains.financial import FinancialMemoryStore
from sovereign.memory.domains.health_routine import (
    HealthMetric,
    HealthProfile,
    HealthRoutineMemoryStore,
    Routine,
)
from sovereign.memory.domains.identity import IdentityMemoryStore, IdentityRecord
from sovereign.memory.domains.inventory import InventoryItem, InventoryMemoryStore
from sovereign.memory.domains.learning import LearningItem, LearningMemoryStore, SkillProgress
from sovereign.memory.domains.legal_compliance import (
    ComplianceRequirement,
    Contract,
    LegalComplianceMemoryStore,
)
from sovereign.memory.domains.operational import SOP, Checklist, OperationalMemoryStore
from sovereign.memory.domains.project import ProjectMemoryStore
from sovereign.memory.domains.relationship import Contact, Interaction, RelationshipMemoryStore
from sovereign.memory.domains.research import (
    ResearchFinding,
    ResearchMemoryStore,
    ResearchProject,
    ResearchSource,
)

__all__ = [
    "IdentityRecord", "IdentityMemoryStore",
    "DiaryEntry", "DiaryMemoryStore",
    "BrandIdentity", "BrandAsset", "BrandMemoryStore",
    "DecisionRecord", "DecisionMemoryStore",
    "HealthMetric", "Routine", "HealthProfile", "HealthRoutineMemoryStore",
    "InventoryItem", "InventoryMemoryStore",
    "LearningItem", "SkillProgress", "LearningMemoryStore",
    "Contract", "ComplianceRequirement", "LegalComplianceMemoryStore",
    "SOP", "Checklist", "OperationalMemoryStore",
    "ContentPiece", "ContentCalendarEntry", "ContentMemoryStore",
    "Contact", "Interaction", "RelationshipMemoryStore",
    "ResearchProject", "ResearchFinding", "ResearchSource", "ResearchMemoryStore",
    "FinancialMemoryStore",
    "ProjectMemoryStore",
    "BusinessIdea", "BusinessIdeaMemoryStore",
    "NextAction", "NextActionStore",
    "RedFlag", "PersonalConstitutionStore",
    "PersonalVersion", "PersonalVersionStore",
]
