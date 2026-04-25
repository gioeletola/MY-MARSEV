"""PersonalResearch Center — personal research & intelligence."""
from sovereign.centers.simple_center import SimpleCenter


class PersonalResearchCenter(SimpleCenter):
    CENTER_ID = 'personal_research_centre'
    DESCRIPTION = 'Personal Research & Intelligence'
    PRIMARY_MODE = 'personal'
    AGENTS = ['knowledge_search', 'knowledge_synthesis', 'insight_agent', 'reading_list', 'personal_archivist']
    DOMAIN_MAP = {'search': 'knowledge_search', 'synthesis': 'knowledge_synthesis', 'insight': 'insight_agent', 'reading': 'reading_list', 'archive': 'personal_archivist'}
    DEFAULT_AGENT = 'knowledge_search'

center = PersonalResearchCenter()
