"""Cultural Center — cultural and intellectual development."""
from sovereign.centers.simple_center import SimpleCenter


class CulturalCenter(SimpleCenter):
    CENTER_ID = "cultural_centre"
    DESCRIPTION = "Cultural & Intellectual Development"
    PRIMARY_MODE = "personal"
    AGENTS = ["cultural_intelligence_chief", "canon_builder", "idea_lineage", "reference_taste", "high_culture_bridge", "concept_genealogy", "skill_gap", "mastery_tracker", "intellectual_synthesis"]
    DOMAIN_MAP = {"canon": "canon_builder", "idea": "idea_lineage", "taste": "reference_taste", "culture": "high_culture_bridge", "skill": "skill_gap", "mastery": "mastery_tracker", "intellect": "intellectual_synthesis"}
    DEFAULT_AGENT = "cultural_intelligence_chief"

center = CulturalCenter()
