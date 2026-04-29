"""Hash Tool — compute and verify cryptographic hashes."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Any

from sovereign.tools.base_tool import BaseTool, ToolSchema


class HashTool(BaseTool):
    """Compute MD5/SHA/BLAKE2 hashes, verify integrity, generate tokens."""

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="hash_tool",
            description="Compute cryptographic hashes (MD5, SHA-256, SHA-512, BLAKE2), verify checksums, and generate secure tokens.",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["hash", "verify", "generate_token", "hmac_sign", "list_algorithms"],
                        "description": "hash | verify | generate_token | hmac_sign | list_algorithms",
                    },
                    "text": {"type": "string", "description": "Text to hash"},
                    "algorithm": {"type": "string", "description": "md5 | sha1 | sha256 | sha512 | blake2b | blake2s (default: sha256)"},
                    "expected_hash": {"type": "string", "description": "Hash to verify against"},
                    "length": {"type": "integer", "description": "Token length in bytes (default 32)"},
                    "secret": {"type": "string", "description": "HMAC secret key"},
                },
                "required": ["action"],
            },
        )

    _ALGORITHMS = {"md5", "sha1", "sha256", "sha512", "blake2b", "blake2s"}

    async def execute(
        self,
        action: str,
        text: str = "",
        algorithm: str = "sha256",
        expected_hash: str = "",
        length: int = 32,
        secret: str = "",
        **_: Any,
    ) -> Any:
        try:
            if action == "hash":
                return self._hash(text, algorithm)
            if action == "verify":
                return self._verify(text, algorithm, expected_hash)
            if action == "generate_token":
                return self._generate_token(length)
            if action == "hmac_sign":
                return self._hmac_sign(text, secret, algorithm)
            if action == "list_algorithms":
                return {"result": sorted(self._ALGORITHMS), "error": None}
            return {"result": None, "error": f"Unknown action: {action}"}
        except Exception as exc:
            return {"result": None, "error": str(exc)}

    def _hash(self, text: str, algorithm: str) -> dict:
        algo = algorithm.lower()
        if algo not in self._ALGORITHMS:
            return {"result": None, "error": f"Unsupported algorithm: {algorithm}. Use: {sorted(self._ALGORITHMS)}"}
        data = text.encode("utf-8")
        if algo == "blake2b":
            h = hashlib.blake2b(data).hexdigest()
        elif algo == "blake2s":
            h = hashlib.blake2s(data).hexdigest()
        else:
            h = hashlib.new(algo, data).hexdigest()
        return {"result": h, "algorithm": algo, "input_length": len(text), "error": None}

    def _verify(self, text: str, algorithm: str, expected: str) -> dict:
        result = self._hash(text, algorithm)
        if result["error"]:
            return result
        computed = result["result"]
        matched = hmac.compare_digest(computed.lower(), expected.lower())
        return {"result": matched, "computed": computed, "expected": expected, "error": None}

    def _generate_token(self, length: int) -> dict:
        n = max(8, min(length, 256))
        token_hex = secrets.token_hex(n)
        token_url = secrets.token_urlsafe(n)
        return {"result": token_hex, "url_safe": token_url, "bytes": n, "error": None}

    def _hmac_sign(self, text: str, secret: str, algorithm: str) -> dict:
        algo = algorithm.lower()
        if algo not in {"sha256", "sha512", "sha1"}:
            algo = "sha256"
        h = hmac.new(secret.encode("utf-8"), text.encode("utf-8"), algo)
        return {"result": h.hexdigest(), "algorithm": algo, "error": None}
