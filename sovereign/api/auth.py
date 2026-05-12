"""JWT auth — HMAC-SHA256, no external library.

Usage::
    token = create_token({"sub": "admin"})
    payload = verify_token(token)                 # raises ValueError if invalid

FastAPI dependency::
    @app.get("/private")
    async def private(user=Depends(require_auth)):
        ...
"""
from __future__ import annotations

import base64
import collections
import hashlib
import hmac
import json
import logging
import os
import threading
import time

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# Rate limiter — simple in-memory sliding window (per IP)
# ---------------------------------------------------------------------------

_rate_lock = threading.Lock()
_attempts: dict[str, list[float]] = collections.defaultdict(list)

_RATE_WINDOW_S = 300.0   # 5-minute window
_RATE_MAX      = 10      # max login attempts per window


def check_rate_limit(ip: str) -> bool:
    """Return True if the IP is within limits, False if rate-limited."""
    now = time.time()
    cutoff = now - _RATE_WINDOW_S
    with _rate_lock:
        _attempts[ip] = [t for t in _attempts[ip] if t > cutoff]
        if len(_attempts[ip]) >= _RATE_MAX:
            return False
        _attempts[ip].append(now)
        return True


def reset_rate_limit(ip: str) -> None:
    """Reset attempts after a successful login."""
    with _rate_lock:
        _attempts.pop(ip, None)


# ---------------------------------------------------------------------------
# Token revocation blacklist (in-memory, cleared on restart)
# ---------------------------------------------------------------------------

_revoked_lock = threading.Lock()
_revoked_jtis: dict[str, float] = {}   # jti → expiry epoch; pruned on access


def _prune_revoked() -> None:
    """Remove expired entries from the blacklist (called under lock)."""
    now = time.time()
    expired = [jti for jti, exp in _revoked_jtis.items() if exp < now]
    for jti in expired:
        del _revoked_jtis[jti]


def revoke_token(jti: str, exp: float) -> None:
    """Add a token's jti to the revocation blacklist until it expires."""
    with _revoked_lock:
        _prune_revoked()
        _revoked_jtis[jti] = exp


def is_revoked(jti: str) -> bool:
    """Return True if the token has been explicitly revoked."""
    with _revoked_lock:
        _prune_revoked()
        return jti in _revoked_jtis


# ---------------------------------------------------------------------------
# Secret key — lazy validation; never falls back to a default
# ---------------------------------------------------------------------------

_MIN_KEY_LEN = 32  # characters


def _get_secret_key() -> str:
    """Return AUTH_SECRET_KEY, raising ValueError if missing or too short.

    Called at token creation/verification time (not at import) so the module
    can be imported safely in CI environments where the key is not set.
    """
    key = os.environ.get("AUTH_SECRET_KEY", "")
    if not key or len(key) < _MIN_KEY_LEN:
        raise ValueError(
            f"AUTH_SECRET_KEY missing or too short ({len(key)} chars; minimum {_MIN_KEY_LEN}). "
            "Set a 64-char random string: "
            "python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    return key


# ---------------------------------------------------------------------------
# Production-safe startup check
# ---------------------------------------------------------------------------

def assert_production_ready() -> None:
    """Call during server startup; raises RuntimeError if config is insecure in production."""
    if os.environ.get("SOVEREIGN_ENV", "").lower() != "production":
        return
    errors: list[str] = []
    auth_key = os.environ.get("AUTH_SECRET_KEY", "")
    if not auth_key:
        errors.append(
            "AUTH_SECRET_KEY is not set "
            "(generate: python -c \"import secrets; print(secrets.token_hex(32))\")"
        )
    elif len(auth_key) < _MIN_KEY_LEN:
        errors.append(
            f"AUTH_SECRET_KEY is too short ({len(auth_key)} chars; minimum {_MIN_KEY_LEN})"
        )
    sovereign_pw = os.environ.get("SOVEREIGN_PASSWORD", "")
    if not sovereign_pw:
        errors.append("SOVEREIGN_PASSWORD is not set (web UI login password)")
    elif len(sovereign_pw) < 12:
        errors.append(
            f"SOVEREIGN_PASSWORD is too short ({len(sovereign_pw)} chars; minimum 12)"
        )
    secret_mgr_key = os.environ.get("SECRET_MANAGER_KEY", "")
    if not secret_mgr_key:
        errors.append("SECRET_MANAGER_KEY is not set (vault encryption key)")
    elif len(secret_mgr_key) < _MIN_KEY_LEN:
        errors.append(
            f"SECRET_MANAGER_KEY is too short ({len(secret_mgr_key)} chars; minimum {_MIN_KEY_LEN})"
        )
    if errors:
        raise RuntimeError(
            "Refusing to start in production. Configuration errors:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )
    logger.info("Production auth configuration verified (%d secrets present).", 3)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def create_token(payload: dict, exp_seconds: int = 28_800) -> str:
    """Create a signed JWT string (HMAC-SHA256 / HS256). Default expiry: 8 hours.

    Raises ValueError if AUTH_SECRET_KEY is missing or too short.
    """
    import uuid
    secret = _get_secret_key()
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    now = int(time.time())
    body_data = dict(payload, iat=now, exp=now + exp_seconds, jti=str(uuid.uuid4()))
    body = _b64url_encode(json.dumps(body_data).encode())
    sig_input = f"{header}.{body}".encode()
    sig = _b64url_encode(
        hmac.new(secret.encode(), sig_input, hashlib.sha256).digest()
    )
    return f"{header}.{body}.{sig}"


def verify_token(token: str) -> dict:
    """Verify and decode a JWT. Raises ValueError on any failure.

    Explicitly uses HS256 to prevent algorithm-confusion attacks.
    Raises ValueError if AUTH_SECRET_KEY is missing or too short.
    """
    secret = _get_secret_key()
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid token format")
        header, body, sig = parts
        # Guard against algorithm confusion: only accept HS256 tokens.
        try:
            header_data = json.loads(_b64url_decode(header))
        except Exception:
            raise ValueError("Invalid token format")
        if header_data.get("alg") != "HS256":
            raise ValueError("Invalid token algorithm — only HS256 is accepted")
        expected_sig = _b64url_encode(
            hmac.new(
                secret.encode(),
                f"{header}.{body}".encode(),
                hashlib.sha256,
            ).digest()
        )
        if not hmac.compare_digest(sig, expected_sig):
            raise ValueError("Invalid signature")
        payload = json.loads(_b64url_decode(body))
        if payload.get("exp", 0) < time.time():
            raise ValueError("Token expired")
        if is_revoked(payload.get("jti", "")):
            raise ValueError("Token has been revoked")
        return payload
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Token error: {exc}") from exc


async def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """FastAPI dependency — enforces JWT auth on protected routes."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return verify_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )


# ---------------------------------------------------------------------------
# Short-lived WebSocket tickets
# ---------------------------------------------------------------------------

_ws_ticket_lock = threading.Lock()
_ws_tickets: dict[str, float] = {}   # ticket → expiry epoch
_WS_TICKET_TTL = 30.0               # seconds


def _prune_ws_tickets() -> None:
    now = time.time()
    expired = [t for t, exp in _ws_tickets.items() if exp < now]
    for t in expired:
        del _ws_tickets[t]


def create_ws_ticket() -> str:
    """Issue a single-use 30-second ticket for WebSocket authentication."""
    import secrets
    ticket = secrets.token_urlsafe(32)
    with _ws_ticket_lock:
        _prune_ws_tickets()
        _ws_tickets[ticket] = time.time() + _WS_TICKET_TTL
    return ticket


def consume_ws_ticket(ticket: str) -> bool:
    """Consume a WS ticket. Returns True if valid and not yet used."""
    with _ws_ticket_lock:
        _prune_ws_tickets()
        if ticket not in _ws_tickets:
            return False
        del _ws_tickets[ticket]  # single-use: delete on consume
        return True
