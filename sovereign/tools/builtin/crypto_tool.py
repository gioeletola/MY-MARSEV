"""Crypto Tool — hashing, HMAC, symmetric encryption, key derivation (stdlib only)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from typing import Any

from sovereign.tools.base_tool import BaseTool, ToolSchema


class CryptoTool(BaseTool):
    """Cryptographic utilities: hashing, HMAC, token generation, key derivation, constant-time compare."""

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="crypto_tool",
            description="Cryptographic operations: SHA-2/SHA-3 hashing, HMAC, secure token generation, PBKDF2 key derivation, constant-time compare.",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["hash", "hmac", "token", "derive_key", "compare", "random_bytes", "checksum"],
                        "description": "hash|hmac|token|derive_key|compare|random_bytes|checksum",
                    },
                    "data": {"type": "string", "description": "Input data to hash or sign"},
                    "key": {"type": "string", "description": "HMAC key or password for derive_key"},
                    "algorithm": {"type": "string", "description": "Hash algorithm: sha256|sha512|sha3_256|sha3_512|blake2b|md5"},
                    "nbytes": {"type": "integer", "description": "Number of bytes for token/random_bytes (default 32)"},
                    "salt": {"type": "string", "description": "Salt for derive_key (hex-encoded; generated if omitted)"},
                    "iterations": {"type": "integer", "description": "PBKDF2 iterations (default 100000)"},
                    "a": {"type": "string", "description": "First string for constant-time compare"},
                    "b": {"type": "string", "description": "Second string for constant-time compare"},
                    "encoding": {"type": "string", "description": "Output encoding: hex|base64 (default hex)"},
                },
                "required": ["action"],
            },
        )

    async def execute(
        self, action: str, data: str = "", key: str = "", algorithm: str = "sha256",
        nbytes: int = 32, salt: str = "", iterations: int = 100_000,
        a: str = "", b: str = "", encoding: str = "hex", **_: Any,
    ) -> Any:
        try:
            if action == "hash":
                return self._hash(data, algorithm, encoding)
            if action == "hmac":
                return self._hmac(data, key, algorithm, encoding)
            if action == "token":
                n = max(1, min(nbytes, 256))
                token = secrets.token_urlsafe(n)
                return {"result": token, "bytes": n, "error": None}
            if action == "random_bytes":
                n = max(1, min(nbytes, 256))
                raw = os.urandom(n)
                out = base64.b64encode(raw).decode() if encoding == "base64" else raw.hex()
                return {"result": out, "bytes": n, "error": None}
            if action == "derive_key":
                return self._derive_key(key, salt, iterations, nbytes, encoding)
            if action == "compare":
                result = hmac.compare_digest(a.encode(), b.encode())
                return {"result": result, "error": None}
            if action == "checksum":
                return self._checksum(data)
            return {"result": None, "error": f"Unknown action: {action}"}
        except Exception as exc:
            return {"result": None, "error": str(exc)}

    def _hash(self, data: str, algorithm: str, encoding: str) -> dict:
        supported = {"sha256", "sha512", "sha3_256", "sha3_512", "blake2b", "sha1", "md5"}
        if algorithm not in supported:
            return {"result": None, "error": f"Unsupported algorithm: {algorithm}. Use: {sorted(supported)}"}
        h = hashlib.new(algorithm, data.encode())
        digest = h.digest()
        out = base64.b64encode(digest).decode() if encoding == "base64" else digest.hex()
        return {"result": out, "algorithm": algorithm, "length": len(digest), "error": None}

    def _hmac(self, data: str, key: str, algorithm: str, encoding: str) -> dict:
        if not key:
            return {"result": None, "error": "key is required for hmac"}
        algo_map = {"sha256": hashlib.sha256, "sha512": hashlib.sha512, "sha1": hashlib.sha1}
        algo_fn = algo_map.get(algorithm)
        if algo_fn is None:
            return {"result": None, "error": f"HMAC supports: {list(algo_map.keys())}"}
        mac = hmac.new(key.encode(), data.encode(), algo_fn)
        digest = mac.digest()
        out = base64.b64encode(digest).decode() if encoding == "base64" else digest.hex()
        return {"result": out, "algorithm": algorithm, "error": None}

    def _derive_key(self, password: str, salt_hex: str, iterations: int, dklen: int, encoding: str) -> dict:
        salt_bytes = bytes.fromhex(salt_hex) if salt_hex else os.urandom(16)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt_bytes, iterations, dklen=dklen)
        out = base64.b64encode(dk).decode() if encoding == "base64" else dk.hex()
        return {
            "result": out,
            "salt": salt_bytes.hex(),
            "iterations": iterations,
            "dklen": dklen,
            "error": None,
        }

    def _checksum(self, data: str) -> dict:
        encoded = data.encode()
        return {
            "result": {
                "md5": hashlib.md5(encoded).hexdigest(),
                "sha1": hashlib.sha1(encoded).hexdigest(),
                "sha256": hashlib.sha256(encoded).hexdigest(),
                "crc32": format(hash(data) & 0xFFFFFFFF, "08x"),
            },
            "size_bytes": len(encoded),
            "error": None,
        }
