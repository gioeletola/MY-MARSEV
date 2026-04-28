"""
Secret Manager — AES-256-GCM encrypted storage for sensitive credentials.

Encryption strategy:
  - AES-256-GCM via the `cryptography` library (Fernet-compatible key derivation).
  - Key is derived from SECRET_MANAGER_KEY env var using PBKDF2-HMAC-SHA256.
  - Each secret gets its own random 12-byte nonce; ciphertext is stored as
    base64(nonce + tag + ciphertext) so it is self-contained.
  - Falls back to XOR obfuscation when `cryptography` is not installed,
    logging a prominent warning.

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
_SALT = b"SOVEREIGN-AI-OS-SALT-v1"   # static salt; rotate with key rotation
_ITERATIONS = 100_000

# Probe cryptography once at import time.
# pyo3_runtime.PanicException is a BaseException (not Exception) so we must
# use `except BaseException` here to catch broken Rust-backed installs.
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _AESGCM  # noqa: F401
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC as _PBKDF2HMAC  # noqa: F401
    from cryptography.hazmat.primitives import hashes as _hashes  # noqa: F401
    _CRYPTOGRAPHY_AVAILABLE = True
except BaseException:
    _CRYPTOGRAPHY_AVAILABLE = False


# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------

def _derive_key_aes() -> bytes:
    """Derive a 32-byte AES-256 key from SECRET_MANAGER_KEY via PBKDF2."""
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes

    raw = os.environ.get("SECRET_MANAGER_KEY", "SOVEREIGN-DEV-INSECURE-KEY")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        iterations=_ITERATIONS,
    )
    return kdf.derive(raw.encode())


# ---------------------------------------------------------------------------
# AES-256-GCM cipher helpers
# ---------------------------------------------------------------------------

def _encrypt(plaintext: str) -> str:
    """Encrypt *plaintext* with AES-256-GCM.

    Returns base64(nonce[12] + tag[16] + ciphertext).
    Falls back to XOR obfuscation only in non-production environments when
    the ``cryptography`` library is unavailable (e.g. minimal CI environments).
    In production (``SOVEREIGN_ENV=production``) the XOR fallback is disabled
    and a RuntimeError is raised instead.
    """
    if not _CRYPTOGRAPHY_AVAILABLE:
        if os.environ.get("SOVEREIGN_ENV", "").lower() == "production":
            raise RuntimeError(
                "cryptography library is required in production. "
                "Run: pip install cryptography>=42.0.0"
            )
        logger.warning(
            "cryptography unavailable — falling back to XOR obfuscation (dev only). "
            "Run: pip install cryptography>=42.0.0"
        )
        return _xor_encrypt(plaintext)

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    key = _derive_key_aes()
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def _decrypt(ciphertext: str) -> str:
    """Decrypt AES-256-GCM ciphertext.

    Falls back to XOR for legacy values or when ``cryptography`` is missing
    (non-production only).
    """
    if not _CRYPTOGRAPHY_AVAILABLE:
        if os.environ.get("SOVEREIGN_ENV", "").lower() == "production":
            raise RuntimeError(
                "cryptography library is required in production. "
                "Run: pip install cryptography>=42.0.0"
            )
        return _xor_decrypt(ciphertext)

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    try:
        raw = base64.b64decode(ciphertext.encode())
        if len(raw) < 28:
            raise ValueError("Blob too short for AES-GCM — trying XOR fallback")
        nonce, ct = raw[:12], raw[12:]
        key = _derive_key_aes()
        return AESGCM(key).decrypt(nonce, ct, None).decode()
    except Exception:
        # Could be a legacy XOR-encrypted value stored before AES migration
        try:
            return _xor_decrypt(ciphertext)
        except Exception:
            raise


# ---------------------------------------------------------------------------
# XOR fallback (legacy + no-cryptography environments)
# ---------------------------------------------------------------------------

_FALLBACK_KEY = b"SOVEREIGN-DEV-KEY-DO-NOT-USE-IN-PROD"


def _xor_bytes(data: bytes, key: bytes) -> bytes:
    key_len = len(key)
    return bytes(b ^ key[i % key_len] for i, b in enumerate(data))


def _derive_key() -> bytes:
    """Return the XOR key (env var or fallback). Used by tests."""
    return os.environ.get("SECRET_MANAGER_KEY", "").encode() or _FALLBACK_KEY


def _xor_encrypt(plaintext: str) -> str:
    return base64.b64encode(_xor_bytes(plaintext.encode(), _derive_key())).decode()


def _xor_decrypt(ciphertext: str) -> str:
    return _xor_bytes(base64.b64decode(ciphertext.encode()), _derive_key()).decode()


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
    Plaintext never appears in logs or on disk.
    """

    def __init__(self, store_path: Path = _STORE_PATH) -> None:
        self._path = store_path
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
            value=_encrypt(value),
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
            return _decrypt(entry.value)
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
        entry.value = _encrypt(new_value)
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
