"""Auth system — session tokens using HMAC-SHA256."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import pathlib
import time
import uuid
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_DEFAULT_REVOKE_PATH = pathlib.Path("data/memory/revoked_tokens.json")
_FALLBACK_KEY = "sovereign-ai-os-default-key-change-me"


@dataclass
class TokenPayload:
    subject: str
    role: str
    issued_at: float
    expires_at: float
    session_id: str


class AuthManager:
    def __init__(self, revoke_path: str | pathlib.Path = _DEFAULT_REVOKE_PATH) -> None:
        self._path = pathlib.Path(revoke_path)
        self._revoked: set[str] = set()
        self._load_revoked()

    @property
    def _key(self) -> str:
        return os.environ.get("AUTH_SECRET_KEY", _FALLBACK_KEY)

    def create_token(self, subject: str, role: str, expires_in_seconds: int = 86400) -> str:
        now = time.time()
        payload = TokenPayload(
            subject=subject,
            role=role,
            issued_at=now,
            expires_at=now + expires_in_seconds,
            session_id=str(uuid.uuid4())[:12],
        )
        header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').decode()
        body = base64.urlsafe_b64encode(
            json.dumps({
                "sub": payload.subject,
                "role": payload.role,
                "iat": payload.issued_at,
                "exp": payload.expires_at,
                "sid": payload.session_id,
            }).encode()
        ).decode()
        sig = self._sign(f"{header}.{body}")
        return f"{header}.{body}.{sig}"

    def verify_token(self, token: str) -> TokenPayload | None:
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None
            header, body, sig = parts
            expected_sig = self._sign(f"{header}.{body}")
            if not hmac.compare_digest(sig, expected_sig):
                logger.warning("Auth: invalid token signature")
                return None
            if self.is_revoked(token):
                return None
            data = json.loads(base64.urlsafe_b64decode(body + "==").decode())
            if time.time() > data["exp"]:
                logger.debug("Auth: token expired for %s", data.get("sub"))
                return None
            return TokenPayload(
                subject=data["sub"],
                role=data["role"],
                issued_at=data["iat"],
                expires_at=data["exp"],
                session_id=data["sid"],
            )
        except Exception as exc:
            logger.warning("Auth: token verification failed: %s", exc)
            return None

    def revoke_token(self, token: str) -> None:
        self._revoked.add(self._token_hash(token))
        self._persist_revoked()

    def is_revoked(self, token: str) -> bool:
        return self._token_hash(token) in self._revoked

    def _sign(self, data: str) -> str:
        h = hmac.new(self._key.encode(), data.encode(), hashlib.sha256)
        return base64.urlsafe_b64encode(h.digest()).decode().rstrip("=")

    def _token_hash(self, token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()[:16]

    def _persist_revoked(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(list(self._revoked)), encoding="utf-8")
        except Exception as exc:
            logger.error("Auth: revoke persist failed: %s", exc)

    def _load_revoked(self) -> None:
        if not self._path.exists():
            return
        try:
            self._revoked = set(json.loads(self._path.read_text(encoding="utf-8")))
        except Exception as exc:
            logger.warning("Auth: load revoked failed: %s", exc)
