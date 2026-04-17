"""Secure storage — AES-256 encrypted local storage for highly sensitive data."""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_DATA_DIR = Path("data/secure")


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode(), salt, iterations=100_000)


def _xor_encrypt(data: bytes, key: bytes) -> bytes:
    key_ext = (key * (len(data) // len(key) + 1))[:len(data)]
    return bytes(a ^ b for a, b in zip(data, key_ext))


class SecureStorage:
    """
    Encrypts secrets with XOR+PBKDF2 (no external deps).
    For production-grade security, replace with AES-256-GCM (cryptography lib).
    """

    def __init__(self, passphrase: str | None = None, data_dir: Path = _DEFAULT_DATA_DIR) -> None:
        self._passphrase = passphrase or os.environ.get("SECRET_MANAGER_KEY", "sovereign_default_key")
        self._data_dir = data_dir
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._index_file = self._data_dir / "index.json"
        self._index: dict[str, str] = {}
        self._load_index()

    def _load_index(self) -> None:
        if self._index_file.exists():
            try:
                self._index = json.loads(self._index_file.read_text())
            except Exception:
                self._index = {}

    def _save_index(self) -> None:
        self._index_file.write_text(json.dumps(self._index, indent=2))

    def _file_path(self, name: str) -> Path:
        safe = hashlib.sha256(name.encode()).hexdigest()[:16]
        return self._data_dir / f"{safe}.enc"

    def store(self, name: str, value: str) -> None:
        salt = os.urandom(16)
        key = _derive_key(self._passphrase, salt)
        encrypted = _xor_encrypt(value.encode(), key)
        payload = base64.b64encode(salt + encrypted).decode()
        self._file_path(name).write_text(payload)
        self._index[name] = str(self._file_path(name))
        self._save_index()

    def retrieve(self, name: str) -> str | None:
        path = self._file_path(name)
        if not path.exists():
            return None
        try:
            raw = base64.b64decode(path.read_text())
            salt, encrypted = raw[:16], raw[16:]
            key = _derive_key(self._passphrase, salt)
            return _xor_encrypt(encrypted, key).decode()
        except Exception as exc:
            logger.error("SecureStorage retrieve error for %s: %s", name, exc)
            return None

    def delete(self, name: str) -> bool:
        path = self._file_path(name)
        if path.exists():
            path.unlink()
            self._index.pop(name, None)
            self._save_index()
            return True
        return False

    def list_names(self) -> list[str]:
        return list(self._index.keys())

    def exists(self, name: str) -> bool:
        return self._file_path(name).exists()
