"""Vault Center — personal vault & document security."""
from sovereign.centers.simple_center import SimpleCenter


class VaultCenter(SimpleCenter):
    CENTER_ID = 'vault_centre'
    DESCRIPTION = 'Personal Vault & Document Security'
    PRIMARY_MODE = 'personal'
    AGENTS = ['document_manager', 'document_readiness', 'backup_integrity']
    DOMAIN_MAP = {'document': 'document_manager', 'doc': 'document_manager', 'backup': 'backup_integrity', 'readiness': 'document_readiness'}
    DEFAULT_AGENT = 'document_manager'

center = VaultCenter()
