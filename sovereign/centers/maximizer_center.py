"""Maximizer Center — personal maximizer & performance."""
from sovereign.centers.simple_center import SimpleCenter

class MaximizerCenter(SimpleCenter):
    CENTER_ID = 'maximizer_centre'
    DESCRIPTION = 'Personal Maximizer & Performance'
    PRIMARY_MODE = 'personal'
    AGENTS = ['personal_maximizer_chief', 'maximizer_agent', 'productivity_auditor', 'attention_auditor', 'deep_work_scheduler']
    DOMAIN_MAP = {'productivity': 'productivity_auditor', 'attention': 'attention_auditor', 'deep work': 'deep_work_scheduler', 'maximiz': 'maximizer_agent'}
    DEFAULT_AGENT = 'personal_maximizer_chief'

center = MaximizerCenter()
