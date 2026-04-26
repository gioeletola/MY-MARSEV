"""Vault Center — personal vault, document security, and readiness."""
from sovereign.centers.simple_center import SimpleCenter


class VaultCenter(SimpleCenter):
    CENTER_ID = "vault_centre"
    DESCRIPTION = "Personal Vault & Document Security"
    PRIMARY_MODE = "personal"
    AGENTS = ["document_manager", "document_readiness", "backup_integrity"]
    DOMAIN_MAP = {
        "document": "document_manager",
        "doc": "document_manager",
        "passport": "document_manager",
        "id": "document_manager",
        "backup": "backup_integrity",
        "readiness": "document_readiness",
        "emergency": "document_readiness",
        "vault": "document_manager",
        "secure": "document_manager",
    }
    DEFAULT_AGENT = "document_manager"
    CAPABILITIES = [
        "Document registry: track expiry dates for IDs, passports, and licences",
        "Document readiness score: ready-to-travel, ready-to-relocate status",
        "Backup integrity: verify all critical docs are backed up and accessible",
        "Emergency kit: one-click list of documents needed for any scenario",
        "Expiry alerts: 90/30/7 day notifications before document renewal",
    ]


center = VaultCenter()
