"""Shared Google OAuth2 token refresh helper for Gmail and Calendar connectors."""
from __future__ import annotations

import logging
import os
import time

logger = logging.getLogger(__name__)

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_token_cache: dict[str, tuple[str, float]] = {}


async def refresh_google_token(
    refresh_token: str,
    client_id: str | None = None,
    client_secret: str | None = None,
) -> str | None:
    """Exchange a refresh_token for a new access_token. Returns None on failure."""
    cid = client_id or os.getenv("GOOGLE_CLIENT_ID", "")
    csecret = client_secret or os.getenv("GOOGLE_CLIENT_SECRET", "")
    if not cid or not csecret:
        logger.warning("OAuthRefresh: GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET not set")
        return None
    cached = _token_cache.get(refresh_token)
    if cached:
        access_token, expires_at = cached
        if time.time() < expires_at - 60:
            return access_token
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                _TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": cid,
                    "client_secret": csecret,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                access_token = data["access_token"]
                expires_in = int(data.get("expires_in", 3600))
                _token_cache[refresh_token] = (access_token, time.time() + expires_in)
                logger.info("OAuthRefresh: token refreshed (expires in %ds)", expires_in)
                return access_token
            logger.error("OAuthRefresh: HTTP %d — %s", resp.status_code, resp.text[:200])
    except Exception as exc:
        logger.error("OAuthRefresh: %s", exc)
    return None


async def ensure_fresh_token(
    access_token: str,
    refresh_token: str,
    client_id: str | None = None,
    client_secret: str | None = None,
) -> str:
    """Return a valid access token, refreshing proactively when near expiry."""
    if not refresh_token:
        return access_token
    cached = _token_cache.get(refresh_token)
    if cached:
        _tok, expires_at = cached
        if time.time() < expires_at - 60:
            return _tok
    new_token = await refresh_google_token(refresh_token, client_id, client_secret)
    return new_token or access_token


def invalidate(refresh_token: str | None = None) -> None:
    """Evict one or all cached tokens."""
    if refresh_token:
        _token_cache.pop(refresh_token, None)
    else:
        _token_cache.clear()
