"""Governance Center — system governance & policy."""
from sovereign.centers.simple_center import SimpleCenter

class GovernanceCenter(SimpleCenter):
    CENTER_ID = 'governance_centre'
    DESCRIPTION = 'System Governance & Policy'
    PRIMARY_MODE = 'command'
    AGENTS = ['sovereign_auditor', 'permission_auditor', 'compliance_agent']
    DOMAIN_MAP = {'audit': 'sovereign_auditor', 'permission': 'permission_auditor', 'compliance': 'compliance_agent', 'governance': 'sovereign_auditor', 'policy': 'sovereign_auditor'}
    DEFAULT_AGENT = 'sovereign_auditor'

center = GovernanceCenter()
