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
# Secret key — fail hard in production if not configured
# ---------------------------------------------------------------------------

_DEFAULT_SECRET = "sovereign-change-me-in-production"
_WARNED_DEFAULT = False


def _secret() -> str:
    global _WARNED_DEFAULT
    val = os.environ.get("AUTH_SECRET_KEY")
    if val:
        return val
    if os.environ.get("SOVEREIGN_ENV", "").lower() == "production":
        raise RuntimeError(
            "AUTH_SECRET_KEY must be set in production (SOVEREIGN_ENV=production). "
            "Generate with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    if not _WARNED_DEFAULT:
        _WARNED_DEFAULT = True
        logger.warning(
            "AUTH_SECRET_KEY is not set — using insecure default. "
            "Set AUTH_SECRET_KEY in your .env before exposing this service."
        )
    return _DEFAULT_SECRET


# ---------------------------------------------------------------------------
# Production-safe startup check
# ---------------------------------------------------------------------------

def assert_production_ready() -> None:
    """Call during server startup; raises RuntimeError if config is insecure in production."""
    if os.environ.get("SOVEREIGN_ENV", "").lower() != "production":
        return
    missing = []
    if not os.environ.get("AUTH_SECRET_KEY"):
        missing.append("AUTH_SECRET_KEY (random 64-char hex: python -c \"import secrets; print(secrets.token_hex(32))\")")
    if not os.environ.get("SOVEREIGN_PASSWORD"):
        missing.append("SOVEREIGN_PASSWORD (web UI login password)")
    if not os.environ.get("SECRET_MANAGER_KEY"):
        missing.append("SECRET_MANAGER_KEY (vault encryption key)")
    if missing:
        raise RuntimeError(
            "Refusing to start in production. Missing required secrets:\n"
            + "\n".join(f"  - {m}" for m in missing)
        )
    logger.info("Production auth configuration verified (%d secrets present).", 3)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def create_token(payload: dict, exp_seconds: int = 28_800) -> str:
    """Create a signed JWT string. Default expiry: 8 hours."""
    import uuid
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    now = int(time.time())
    body_data = dict(payload, iat=now, exp=now + exp_seconds, jti=str(uuid.uuid4()))
    body = _b64url_encode(json.dumps(body_data).encode())
    sig_input = f"{header}.{body}".encode()
    sig = _b64url_encode(
        hmac.new(_secret().encode(), sig_input, hashlib.sha256).digest()
    )
    return f"{header}.{body}.{sig}"


def verify_token(token: str) -> dict:
    """Verify and decode a JWT. Raises ValueError on any failure."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid token format")
        header, body, sig = parts
        expected_sig = _b64url_encode(
            hmac.new(
                _secret().encode(),
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
