"""
Secure storage — field-level encrypted storage wrapping SecretManager.

Sensitivity levels:
  low    — XOR obfuscation (fast, no deps, minimal security)
  medium — AES-256-GCM (cryptography library, recommended)
  high   — AES-256-GCM + automatic key rotation on each write

Public API:
  storage = SecureStorage()
  storage.store_encrypted(namespace, key, value, sensitivity="medium")
  storage.retrieve_encrypted(namespace, key) → str | None
  storage.delete_encrypted(namespace, key) → bool
  storage.list_encrypted(namespace) → list[str]

Also provides backward-compatible store/retrieve/delete/list_names API.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

_DEFAULT_DATA_DIR = Path("data/secure")
_SENSITIVITY = Literal["low", "medium", "high"]


# ---------------------------------------------------------------------------
# Crypto helpers
# ---------------------------------------------------------------------------

def _xor_encrypt(data: bytes, key: bytes) -> bytes:
    key_ext = (key * (len(data) // len(key) + 1))[:len(data)]
    return bytes(a ^ b for a, b in zip(data, key_ext))


def _derive_key_pbkdf2(passphrase: str, salt: bytes, length: int = 32) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode(), salt, iterations=100_000, dklen=length)


def _try_aes_gcm_encrypt(plaintext: bytes, key: bytes) -> bytes:
    """AES-256-GCM encrypt. Returns nonce(12) + ciphertext_with_tag."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext, None)
    return nonce + ct


def _try_aes_gcm_decrypt(blob: bytes, key: bytes) -> bytes:
    """AES-256-GCM decrypt from nonce(12) + ciphertext_with_tag."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce, ct = blob[:12], blob[12:]
    return AESGCM(key).decrypt(nonce, ct, None)


# Probe once at module load — pyo3_runtime.PanicException is BaseException, not Exception
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _AESGCM_PROBE  # noqa: F401
    _CRYPTO_OK = True
except BaseException:
    _CRYPTO_OK = False


def _is_cryptography_available() -> bool:
    return _CRYPTO_OK


# ---------------------------------------------------------------------------
# Encryption / decryption per sensitivity
# ---------------------------------------------------------------------------

def _encrypt_field(value: str, passphrase: str, sensitivity: str) -> dict:
    """
    Encrypt *value* according to *sensitivity*.

    Returns a dict with:
      sensitivity, method, salt (hex), payload (base64), rotation_id
    """
    raw = value.encode("utf-8")

    if sensitivity == "low" or not _is_cryptography_available():
        if sensitivity != "low":
            logger.warning(
                "SecureStorage: cryptography unavailable — falling back to XOR for sensitivity=%s",
                sensitivity,
            )
        salt = os.urandom(16)
        key = _derive_key_pbkdf2(passphrase, salt)
        encrypted = _xor_encrypt(raw, key)
        return {
            "sensitivity": sensitivity,
            "method": "xor+pbkdf2",
            "salt": salt.hex(),
            "payload": base64.b64encode(encrypted).decode(),
            "rotation_id": str(uuid.uuid4())[:8],
            "encrypted_at": datetime.now(timezone.utc).isoformat(),
        }

    # medium / high — AES-256-GCM
    salt = os.urandom(16)
    key = _derive_key_pbkdf2(passphrase, salt)
    blob = _try_aes_gcm_encrypt(raw, key)
    result = {
        "sensitivity": sensitivity,
        "method": "aes-256-gcm",
        "salt": salt.hex(),
        "payload": base64.b64encode(blob).decode(),
        "rotation_id": str(uuid.uuid4())[:8],
        "encrypted_at": datetime.now(timezone.utc).isoformat(),
    }

    # high: generate a new derived sub-key per rotation (key rotation)
    if sensitivity == "high":
        rotation_salt = os.urandom(16)
        rotation_key = _derive_key_pbkdf2(passphrase + result["rotation_id"], rotation_salt)
        rotated_blob = _try_aes_gcm_encrypt(blob, rotation_key)
        result["rotation_salt"] = rotation_salt.hex()
        result["payload"] = base64.b64encode(rotated_blob).decode()
        result["method"] = "aes-256-gcm+rotation"

    return result


def _decrypt_field(record: dict, passphrase: str) -> str:
    """Decrypt a stored field record back to plaintext."""
    method = record.get("method", "xor+pbkdf2")
    salt = bytes.fromhex(record["salt"])
    payload = base64.b64decode(record["payload"])

    if method == "xor+pbkdf2":
        key = _derive_key_pbkdf2(passphrase, salt)
        return _xor_encrypt(payload, key).decode("utf-8")

    if method == "aes-256-gcm":
        key = _derive_key_pbkdf2(passphrase, salt)
        return _try_aes_gcm_decrypt(payload, key).decode("utf-8")

    if method == "aes-256-gcm+rotation":
        rotation_id = record["rotation_id"]
        rotation_salt = bytes.fromhex(record["rotation_salt"])
        rotation_key = _derive_key_pbkdf2(passphrase + rotation_id, rotation_salt)
        # Decrypt outer rotation layer
        inner_blob = _try_aes_gcm_decrypt(payload, rotation_key)
        # Decrypt inner AES-GCM layer
        key = _derive_key_pbkdf2(passphrase, salt)
        return _try_aes_gcm_decrypt(inner_blob, key).decode("utf-8")

    raise ValueError(f"Unknown encryption method: {method}")


# ---------------------------------------------------------------------------
# SecureStorage
# ---------------------------------------------------------------------------

class SecureStorage:
    """
    Field-level encrypted storage with namespace support.

    Sensitivity levels:
      low    — XOR+PBKDF2 (no external deps)
      medium — AES-256-GCM (requires cryptography library)
      high   — AES-256-GCM + per-write key rotation

    Backward-compatible with old store/retrieve/delete/list_names API.
    """

    def __init__(
        self,
        passphrase: str | None = None,
        data_dir: Path = _DEFAULT_DATA_DIR,
    ) -> None:
        self._passphrase = passphrase or os.environ.get("SECRET_MANAGER_KEY", "sovereign_default_key")
        self._data_dir = data_dir
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._store_file = self._data_dir / "secure_store.json"
        self._store: dict[str, dict[str, dict]] = {}   # namespace → key → record
        self._load()

    # -------------------------------------------------------------------------
    # New namespaced API
    # -------------------------------------------------------------------------

    def store_encrypted(
        self,
        namespace: str,
        key: str,
        value: str,
        sensitivity: str = "medium",
    ) -> None:
        """
        Encrypt and store *value* under namespace/key.

        Args:
            namespace   – logical group (e.g. "finance", "oauth", "user_data")
            key         – field name within namespace
            value       – plaintext value to encrypt
            sensitivity – "low" | "medium" | "high"
        """
        if sensitivity not in ("low", "medium", "high"):
            raise ValueError(f"sensitivity must be low|medium|high, got: {sensitivity!r}")

        record = _encrypt_field(value, self._passphrase, sensitivity)
        if namespace not in self._store:
            self._store[namespace] = {}
        self._store[namespace][key] = record
        self._save()
        logger.debug("SecureStorage: stored %s/%s [%s]", namespace, key, record["method"])

    def retrieve_encrypted(self, namespace: str, key: str) -> str | None:
        """
        Retrieve and decrypt a stored value.

        Returns None if the namespace/key does not exist or decryption fails.
        """
        ns = self._store.get(namespace, {})
        record = ns.get(key)
        if record is None:
            return None
        try:
            return _decrypt_field(record, self._passphrase)
        except Exception as exc:
            logger.error("SecureStorage decrypt error for %s/%s: %s", namespace, key, exc)
            return None

    def delete_encrypted(self, namespace: str, key: str) -> bool:
        """
        Delete a stored value.

        Returns True if the entry existed and was deleted.
        """
        ns = self._store.get(namespace, {})
        if key not in ns:
            return False
        del ns[key]
        if not ns:
            del self._store[namespace]
        self._save()
        logger.debug("SecureStorage: deleted %s/%s", namespace, key)
        return True

    def list_encrypted(self, namespace: str) -> list[str]:
        """Return all keys stored in *namespace*."""
        return list(self._store.get(namespace, {}).keys())

    def list_namespaces(self) -> list[str]:
        """Return all namespaces."""
        return list(self._store.keys())

    def exists(self, namespace: str, key: str) -> bool:
        return key in self._store.get(namespace, {})

    def metadata(self, namespace: str, key: str) -> dict | None:
        """Return metadata (method, sensitivity, timestamps) without decrypting."""
        record = self._store.get(namespace, {}).get(key)
        if record is None:
            return None
        return {
            k: v for k, v in record.items()
            if k not in ("payload", "salt", "rotation_salt")
        }

    # -------------------------------------------------------------------------
    # Backward-compatible flat API
    # -------------------------------------------------------------------------

    def store(self, name: str, value: str) -> None:
        """Backward-compatible: store under 'default' namespace."""
        self.store_encrypted("default", name, value, sensitivity="medium")

    def retrieve(self, name: str) -> str | None:
        """Backward-compatible: retrieve from 'default' namespace."""
        # Try new namespace first, then legacy flat index
        result = self.retrieve_encrypted("default", name)
        if result is not None:
            return result
        # Try legacy flat store
        return self._legacy_retrieve(name)

    def delete(self, name: str) -> bool:
        ok = self.delete_encrypted("default", name)
        if not ok:
            ok = self._legacy_delete(name)
        return ok

    def list_names(self) -> list[str]:
        return self.list_encrypted("default")

    # -------------------------------------------------------------------------
    # Legacy helpers (flat file index from old implementation)
    # -------------------------------------------------------------------------

    def _legacy_retrieve(self, name: str) -> str | None:
        """Try the old per-file XOR scheme."""
        try:
            safe = hashlib.sha256(name.encode()).hexdigest()[:16]
            path = self._data_dir / f"{safe}.enc"
            if not path.exists():
                return None
            import base64
            raw = base64.b64decode(path.read_text())
            salt, encrypted = raw[:16], raw[16:]
            key = _derive_key_pbkdf2(self._passphrase, salt)
            return _xor_encrypt(encrypted, key).decode()
        except Exception:
            return None

    def _legacy_delete(self, name: str) -> bool:
        safe = hashlib.sha256(name.encode()).hexdigest()[:16]
        path = self._data_dir / f"{safe}.enc"
        if path.exists():
            path.unlink()
            return True
        return False

    # -------------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------------

    def _load(self) -> None:
        if not self._store_file.exists():
            self._store = {}
            return
        try:
            self._store = json.loads(self._store_file.read_text())
        except Exception as exc:
            logger.error("SecureStorage load error: %s", exc)
            self._store = {}

    def _save(self) -> None:
        self._store_file.write_text(json.dumps(self._store, indent=2))

    # -------------------------------------------------------------------------
    # Observability
    # -------------------------------------------------------------------------

    def stats(self) -> dict:
        total = sum(len(keys) for keys in self._store.values())
        return {
            "namespaces": len(self._store),
            "total_entries": total,
            "by_namespace": {ns: len(keys) for ns, keys in self._store.items()},
        }
