"""
sovereign/security/secrets.py — compatibility shim for vault CLI commands.

Exposes get_secret_manager() backed by SecretManager in secret_manager.py.
"""
from __future__ import annotations

from sovereign.security.secret_manager import SecretManager

_instance: SecretManager | None = None


def get_secret_manager() -> SecretManager:
    """Return the process-wide SecretManager singleton."""
    global _instance
    if _instance is None:
        _instance = SecretManager()
    return _instance


__all__ = ["SecretManager", "get_secret_manager"]
