"""Partner Center — partner & vendor management."""
from sovereign.centers.simple_center import SimpleCenter

class PartnerCenter(SimpleCenter):
    CENTER_ID = 'partner_centre'
    DESCRIPTION = 'Partner & Vendor Management'
    PRIMARY_MODE = 'business'
    AGENTS = ['partner_chief', 'procurement_agent', 'approval_collector']
    DOMAIN_MAP = {'partner': 'partner_chief', 'vendor': 'procurement_agent', 'procurement': 'procurement_agent', 'supplier': 'procurement_agent'}
    DEFAULT_AGENT = 'partner_chief'

center = PartnerCenter()
