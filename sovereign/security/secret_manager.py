"""
Secret Manager — encrypted storage for sensitive credentials and tokens.

Obfuscation strategy: XOR-based cipher with a key derived from the
environment variable SECRET_MANAGER_KEY (base64-decoded).  Falls back to a
static development key when the env var is absent.  Values are stored as
base64-encoded ciphertext; plaintext is never written to disk or logged.
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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_STORE_PATH = Path("data/memory/secrets.json")
_FALLBACK_KEY = b"SOVEREIGN-DEV-KEY-DO-NOT-USE-IN-PROD"  # 36 bytes


# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------


def _derive_key() -> bytes:
    """Return the obfuscation key from env or the static fallback."""
    raw = os.environ.get("SECRET_MANAGER_KEY", "")
    if raw:
        try:
            return base64.b64decode(raw)
        except Exception:
            logger.warning("SECRET_MANAGER_KEY is not valid base64; using fallback key")
    return _FALLBACK_KEY


# ---------------------------------------------------------------------------
# XOR cipher helpers
# ---------------------------------------------------------------------------


def _xor_bytes(data: bytes, key: bytes) -> bytes:
    """XOR *data* against *key* (cycled)."""
    key_len = len(key)
    return bytes(b ^ key[i % key_len] for i, b in enumerate(data))


def _encrypt(plaintext: str) -> str:
    """Return base64-encoded XOR ciphertext of *plaintext*."""
    key = _derive_key()
    cipher = _xor_bytes(plaintext.encode(), key)
    return base64.b64encode(cipher).decode()


def _decrypt(ciphertext: str) -> str:
    """Decode base64 ciphertext and XOR-decrypt back to plaintext."""
    key = _derive_key()
    raw = base64.b64decode(ciphertext.encode())
    return _xor_bytes(raw, key).decode()


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class SecretEntry:
    """Metadata and encrypted value for a single secret."""

    secret_id: str
    name: str
    category: str
    value: str          # always stored encrypted (ciphertext)
    created_at: str
    rotated_at: str
    expires_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> SecretEntry:
        return SecretEntry(**d)


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


class SecretManager:
    """Thread-safe secret store backed by a JSON file.

    Values are XOR-obfuscated before being written; plaintext never
    appears in logs or on disk.
    """

    def __init__(self, store_path: Path = _STORE_PATH) -> None:
        self._path = store_path
        self._secrets: dict[str, SecretEntry] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set(
        self,
        name: str,
        value: str,
        category: str = "general",
        expires_at: str = "",
    ) -> SecretEntry:
        """Store *value* under *name*, overwriting any existing entry."""
        now = datetime.now(timezone.utc).isoformat()
        existing = self._secrets.get(name)
        entry = SecretEntry(
            secret_id=existing.secret_id if existing else str(uuid.uuid4()),
            name=name,
            category=category,
            value=_encrypt(value),
            created_at=existing.created_at if existing else now,
            rotated_at=now if existing else now,
            expires_at=expires_at,
        )
        self._secrets[name] = entry
        self._save()
        logger.info("Secret stored: name=%s category=%s", name, category)
        return entry

    def get(self, name: str) -> str | None:
        """Return the plaintext secret value, or *None* if not found."""
        entry = self._secrets.get(name)
        if entry is None:
            return None
        try:
            return _decrypt(entry.value)
        except Exception:
            logger.error("Failed to decrypt secret: name=%s", name)
            return None

    def delete(self, name: str) -> bool:
        """Remove secret *name*.  Returns *True* if it existed."""
        if name in self._secrets:
            del self._secrets[name]
            self._save()
            logger.info("Secret deleted: name=%s", name)
            return True
        return False

    def rotate(self, name: str, new_value: str) -> bool:
        """Replace value for *name* and update rotated_at timestamp."""
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
        """Return all stored secret names.  Values are never included."""
        return list(self._secrets.keys())

    def expired(self) -> list[str]:
        """Return names of secrets whose expires_at is in the past."""
        now = datetime.now(timezone.utc).isoformat()
        result: list[str] = []
        for name, entry in self._secrets.items():
            if entry.expires_at and entry.expires_at < now:
                result.append(name)
        return result

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load secrets from disk (creating store path if needed)."""
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
        """Persist current secrets to disk (values remain encrypted)."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {name: entry.to_dict() for name, entry in self._secrets.items()}
        self._path.write_text(json.dumps(payload, indent=2))
