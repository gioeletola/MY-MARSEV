"""Inventory Center — personal inventory management."""
from sovereign.centers.simple_center import SimpleCenter

class InventoryCenter(SimpleCenter):
    CENTER_ID = 'inventory_centre'
    DESCRIPTION = 'Personal Inventory Management'
    PRIMARY_MODE = 'personal'
    AGENTS = ['inventory_chief', 'personal_inventory_custodian', 'dead_weight', 'possession_rotation']
    DOMAIN_MAP = {'inventory': 'inventory_chief', 'possession': 'personal_inventory_custodian', 'dead weight': 'dead_weight', 'rotation': 'possession_rotation'}
    DEFAULT_AGENT = 'inventory_chief'

center = InventoryCenter()
