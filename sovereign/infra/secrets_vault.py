"""
SecretsVault — layered secret loading with optional AES-256 (Fernet) encryption.

Priority order (highest → lowest):
  1. Environment variables
  2. .secrets file (key=value, one per line)
  3. Encrypted JSON vault at data/vault/secrets.json
"""

from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_VAULT_PATH = Path("data/vault/secrets.json")
_SECRETS_FILE = Path(".secrets")
_MASTER_KEY_ENV = "SECRET_MASTER_KEY"

try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    _CRYPTO_AVAILABLE = True
except ImportError:  # pragma: no cover
    _CRYPTO_AVAILABLE = False
    logger.warning(
        "SecretsVault: 'cryptography' package not installed. "
        "Encrypted vault support is disabled. Only env vars and .secrets file are used."
    )


def _derive_fernet_key(master_key: str) -> bytes:
    """Derive a 32-byte Fernet key from an arbitrary master key string."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"sovereign-vault-salt-v1",
        iterations=100_000,
    )
    raw = kdf.derive(master_key.encode())
    return base64.urlsafe_b64encode(raw)


class SecretsVault:
    """
    Layered secrets store.

    Usage::

        vault = SecretsVault()
        api_key = vault.get("ANTHROPIC_API_KEY")
        vault.set("MY_SECRET", "s3cr3t")
    """

    def __init__(self) -> None:
        self._env_cache: dict[str, str] = {}
        self._file_cache: dict[str, str] = {}
        self._vault_cache: dict[str, str] = {}
        self._fernet: Any = None

        self._load_secrets_file()
        self._init_fernet()
        self._load_vault()

    # ------------------------------------------------------------------
    # Internal loaders
    # ------------------------------------------------------------------

    def _load_secrets_file(self) -> None:
        """Load key=value pairs from .secrets file."""
        if not _SECRETS_FILE.exists():
            return
        try:
            for line in _SECRETS_FILE.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    self._file_cache[key.strip()] = value.strip()
            logger.debug("SecretsVault: loaded %d keys from .secrets", len(self._file_cache))
        except OSError as exc:
            logger.warning("SecretsVault: could not read .secrets file: %s", exc)

    def _init_fernet(self) -> None:
        """Initialise Fernet cipher from SECRET_MASTER_KEY env var."""
        if not _CRYPTO_AVAILABLE:
            return
        master_key = os.environ.get(_MASTER_KEY_ENV, "")
        if not master_key:
            logger.debug(
                "SecretsVault: %s not set — encrypted vault writes/reads disabled.",
                _MASTER_KEY_ENV,
            )
            return
        try:
            fernet_key = _derive_fernet_key(master_key)
            self._fernet = Fernet(fernet_key)
        except Exception as exc:
            logger.warning("SecretsVault: failed to initialise Fernet cipher: %s", exc)

    def _load_vault(self) -> None:
        """Load and decrypt the JSON vault file."""
        if not _VAULT_PATH.exists():
            return
        if self._fernet is None:
            logger.debug("SecretsVault: vault file found but no cipher — skipping encrypted vault.")
            return
        try:
            encrypted_blob = _VAULT_PATH.read_bytes()
            decrypted = self._fernet.decrypt(encrypted_blob)
            data = json.loads(decrypted)
            if isinstance(data, dict):
                self._vault_cache = {k: str(v) for k, v in data.items()}
            logger.debug("SecretsVault: loaded %d keys from encrypted vault.", len(self._vault_cache))
        except InvalidToken:
            logger.warning("SecretsVault: could not decrypt vault — wrong master key?")
        except Exception as exc:
            logger.warning("SecretsVault: error loading vault: %s", exc)

    def _save_vault(self) -> None:
        """Encrypt and persist the vault cache to disk."""
        if self._fernet is None:
            raise RuntimeError(
                "SecretsVault: cannot write encrypted vault — "
                f"set {_MASTER_KEY_ENV} environment variable and ensure 'cryptography' is installed."
            )
        _VAULT_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            plaintext = json.dumps(self._vault_cache).encode()
            encrypted = self._fernet.encrypt(plaintext)
            _VAULT_PATH.write_bytes(encrypted)
            logger.debug("SecretsVault: vault saved (%d keys).", len(self._vault_cache))
        except Exception as exc:
            logger.error("SecretsVault: failed to save vault: %s", exc)
            raise

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str, default: str = "") -> str:
        """
        Return the secret value for *key*.

        Priority: env var > .secrets file > encrypted vault > default.
        Secret values are never logged.
        """
        # 1. Environment variable (highest priority)
        value = os.environ.get(key)
        if value is not None:
            return value

        # 2. .secrets file
        if key in self._file_cache:
            return self._file_cache[key]

        # 3. Encrypted vault
        if key in self._vault_cache:
            return self._vault_cache[key]

        return default

    def set(self, key: str, value: str) -> None:
        """
        Store *key* → *value* in the encrypted vault and persist to disk.

        Does NOT write to env vars or .secrets file.
        Never logs the value.
        """
        self._vault_cache[key] = value
        self._save_vault()
        logger.info("SecretsVault: key '%s' written to encrypted vault.", key)

    def list_keys(self) -> list[str]:
        """
        Return a sorted list of all known secret keys (no values).

        Includes keys from env vars that are already known via the other layers.
        """
        known: set[str] = set()
        known.update(self._file_cache.keys())
        known.update(self._vault_cache.keys())
        # Include env var overrides for known keys only (avoid leaking all env)
        return sorted(known)
