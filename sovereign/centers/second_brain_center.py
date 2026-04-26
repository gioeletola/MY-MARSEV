"""SecondBrain Center — second brain & knowledge management."""
from sovereign.centers.simple_center import SimpleCenter


class SecondBrainCenter(SimpleCenter):
    CENTER_ID = "second_brain_centre"
    DESCRIPTION = "Second Brain & Knowledge Management"
    PRIMARY_MODE = "personal"
    AGENTS = ["second_brain_chief", "personal_archivist", "knowledge_organizer",
              "knowledge_search", "knowledge_synthesis", "insight_agent"]
    DOMAIN_MAP = {
        "knowledge": "knowledge_organizer",
        "search": "knowledge_search",
        "synthesis": "knowledge_synthesis",
        "insight": "insight_agent",
        "archive": "personal_archivist",
        "note": "knowledge_organizer",
        "notes": "knowledge_organizer",
        "capture": "personal_archivist",
        "summarize": "knowledge_synthesis",
        "summary": "knowledge_synthesis",
    }
    DEFAULT_AGENT = "second_brain_chief"
    CAPABILITIES = [
        "Capture and tag new knowledge from any source",
        "Semantic search across all stored notes and documents",
        "Knowledge synthesis: combine sources into coherent summaries",
        "Insight extraction: surface non-obvious connections",
        "Personal archive management: organise, tag, and version notes",
        "Learning path construction from stored knowledge graph",
    ]


center = SecondBrainCenter()
