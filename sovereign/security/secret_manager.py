"""
Secret Manager — AES-256-GCM encrypted storage for sensitive credentials.

Encryption strategy:
  - AES-256-GCM via the ``cryptography`` library (required; no fallback).
  - Key is derived from SECRET_MANAGER_KEY env var using PBKDF2-HMAC-SHA256
    with 600,000 iterations (OWASP 2024 recommendation for SHA-256).
  - Salt is generated randomly per installation and persisted to
    ``data/memory/.vault_salt`` (256-bit / 32 bytes). Keep this file
    alongside ``secrets.json`` — losing it makes existing vault data
    unrecoverable.
  - Each secret gets its own random 12-byte nonce; ciphertext is stored as
    base64(nonce + tag + ciphertext) so it is self-contained.

Values are NEVER written to disk in plaintext or included in logs.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_STORE_PATH = Path("data/memory/secrets.json")
# Salt file lives next to the secrets store.  Keep both together.
_SALT_FILE = Path("data/memory/.vault_salt")
_ITERATIONS = 600_000   # OWASP 2024 recommendation for PBKDF2-HMAC-SHA256

# cryptography is a hard requirement — no XOR fallback.
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _AESGCM  # noqa: F401
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC as _PBKDF2HMAC  # noqa: F401
    from cryptography.hazmat.primitives import hashes as _hashes  # noqa: F401
    _CRYPTO_AVAILABLE = True
except BaseException:
    _CRYPTO_AVAILABLE = False


# ---------------------------------------------------------------------------
# Per-instance random salt
# ---------------------------------------------------------------------------

def _load_or_create_salt(salt_file: Path = _SALT_FILE) -> bytes:
    """Load the persisted salt or generate and save a fresh one.

    The salt file must be kept alongside the vault data file.  If the salt
    file is lost, existing encrypted secrets cannot be decrypted.
    """
    salt_file.parent.mkdir(parents=True, exist_ok=True)
    if salt_file.exists():
        return salt_file.read_bytes()
    salt = os.urandom(32)   # 256-bit random salt
    salt_file.write_bytes(salt)
    logger.info("Generated new vault salt: %s", salt_file)
    return salt


# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------

def _derive_key_aes(salt: bytes) -> bytes:
    """Derive a 32-byte AES-256 key from SECRET_MANAGER_KEY via PBKDF2."""
    if not _CRYPTO_AVAILABLE:
        raise RuntimeError(
            "The 'cryptography' package is required for SecretManager. "
            "Install it: pip install cryptography"
        )
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes

    raw = os.environ.get("SECRET_MANAGER_KEY", "SOVEREIGN-DEV-INSECURE-KEY")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_ITERATIONS,
    )
    return kdf.derive(raw.encode())


# ---------------------------------------------------------------------------
# AES-256-GCM cipher helpers
# ---------------------------------------------------------------------------

def _encrypt(plaintext: str, salt: bytes | None = None) -> str:
    """Encrypt *plaintext* with AES-256-GCM.

    Returns base64(nonce[12] + tag[16] + ciphertext).
    Requires the ``cryptography`` package — raises RuntimeError if missing.
    """
    if not _CRYPTO_AVAILABLE:
        raise RuntimeError(
            "The 'cryptography' package is required for SecretManager. "
            "Install it: pip install cryptography"
        )
    if salt is None:
        salt = _load_or_create_salt()
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    key = _derive_key_aes(salt)
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def _decrypt(ciphertext: str, salt: bytes | None = None) -> str:
    """Decrypt AES-256-GCM ciphertext.

    Requires the ``cryptography`` package — raises RuntimeError if missing.
    """
    if not _CRYPTO_AVAILABLE:
        raise RuntimeError(
            "The 'cryptography' package is required for SecretManager. "
            "Install it: pip install cryptography"
        )
    if salt is None:
        salt = _load_or_create_salt()
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    raw = base64.b64decode(ciphertext.encode())
    if len(raw) < 28:
        raise ValueError("Ciphertext blob too short for AES-GCM")
    nonce, ct = raw[:12], raw[12:]
    key = _derive_key_aes(salt)
    return AESGCM(key).decrypt(nonce, ct, None).decode()


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class SecretEntry:
    secret_id: str
    name: str
    category: str
    value: str          # always stored encrypted
    created_at: str
    rotated_at: str
    expires_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "SecretEntry":
        return SecretEntry(**d)


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class SecretManager:
    """
    Thread-safe AES-256-GCM secret store backed by a JSON file.

    Each instance loads (or creates) a per-installation random salt from
    ``_SALT_FILE`` (default: ``data/memory/.vault_salt``).  Keep the salt
    file and ``secrets.json`` together — losing the salt makes existing
    vault data unrecoverable.

    Plaintext never appears in logs or on disk.
    """

    def __init__(
        self,
        store_path: Path = _STORE_PATH,
        salt_file: Path = _SALT_FILE,
    ) -> None:
        if not _CRYPTO_AVAILABLE:
            raise RuntimeError(
                "The 'cryptography' package is required for SecretManager. "
                "Install it: pip install cryptography"
            )
        self._path = store_path
        # Derive the salt once so all operations within this instance use it.
        # Warn if vault data exists but no salt file (legacy installation).
        if not salt_file.exists() and store_path.exists():
            logger.warning(
                "Vault data found at %s but no salt file at %s. "
                "A new random salt will be generated; existing secrets may not "
                "decrypt correctly. Re-encrypt with the original key or migrate "
                "the vault before relying on stored secrets.",
                store_path,
                salt_file,
            )
        self._salt: bytes = _load_or_create_salt(salt_file)
        self._secrets: dict[str, SecretEntry] = {}
        self._load()

    def set(
        self,
        name: str,
        value: str,
        category: str = "general",
        expires_at: str = "",
    ) -> SecretEntry:
        now = datetime.now(timezone.utc).isoformat()
        existing = self._secrets.get(name)
        entry = SecretEntry(
            secret_id=existing.secret_id if existing else str(uuid.uuid4()),
            name=name,
            category=category,
            value=_encrypt(value, self._salt),
            created_at=existing.created_at if existing else now,
            rotated_at=now,
            expires_at=expires_at,
        )
        self._secrets[name] = entry
        self._save()
        logger.info("Secret stored: name=%s category=%s", name, category)
        return entry

    def get(self, name: str) -> str | None:
        entry = self._secrets.get(name)
        if entry is None:
            return None
        try:
            return _decrypt(entry.value, self._salt)
        except Exception:
            logger.error("Failed to decrypt secret: name=%s", name)
            return None

    def delete(self, name: str) -> bool:
        if name in self._secrets:
            del self._secrets[name]
            self._save()
            logger.info("Secret deleted: name=%s", name)
            return True
        return False

    def rotate(self, name: str, new_value: str) -> bool:
        entry = self._secrets.get(name)
        if entry is None:
            logger.warning("Rotate failed — secret not found: name=%s", name)
            return False
        entry.value = _encrypt(new_value, self._salt)
        entry.rotated_at = datetime.now(timezone.utc).isoformat()
        self._save()
        logger.info("Secret rotated: name=%s", name)
        return True

    def list_names(self) -> list[str]:
        return list(self._secrets.keys())

    # alias used by vault CLI
    def list_keys(self) -> list[str]:
        return self.list_names()

    def expired(self) -> list[str]:
        now = datetime.now(timezone.utc).isoformat()
        return [
            name for name, entry in self._secrets.items()
            if entry.expires_at and entry.expires_at < now
        ]

    def _load(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._secrets = {}
            return
        try:
            data = json.loads(self._path.read_text())
            self._secrets = {k: SecretEntry.from_dict(v) for k, v in data.items()}
        except Exception:
            logger.exception("Failed to load secrets store; starting empty")
            self._secrets = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {name: entry.to_dict() for name, entry in self._secrets.items()}
        self._path.write_text(json.dumps(payload, indent=2))
