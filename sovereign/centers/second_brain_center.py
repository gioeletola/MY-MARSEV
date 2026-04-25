"""SecondBrain Center — second brain & knowledge management."""
from sovereign.centers.simple_center import SimpleCenter

class SecondBrainCenter(SimpleCenter):
    CENTER_ID = 'second_brain_centre'
    DESCRIPTION = 'Second Brain & Knowledge Management'
    PRIMARY_MODE = 'personal'
    AGENTS = ['second_brain_chief', 'personal_archivist', 'knowledge_organizer', 'knowledge_search', 'knowledge_synthesis', 'insight_agent']
    DOMAIN_MAP = {'knowledge': 'knowledge_organizer', 'search': 'knowledge_search', 'synthesis': 'knowledge_synthesis', 'insight': 'insight_agent', 'archive': 'personal_archivist'}
    DEFAULT_AGENT = 'second_brain_chief'

center = SecondBrainCenter()
