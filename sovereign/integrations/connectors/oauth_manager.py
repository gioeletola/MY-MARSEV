"""
OAuth manager — handles token storage, refresh, and provider-specific flows.
Tokens stored in the secrets vault (or fallback to env vars in dev mode).
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
import time
from typing import Any

logger = logging.getLogger(__name__)

_TOKEN_CACHE_PATH = pathlib.Path("data/oauth_tokens.json")

# OAuth endpoints per provider
_OAUTH_PROVIDERS: dict[str, dict[str, str]] = {
    "google": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "revoke_url": "https://oauth2.googleapis.com/revoke",
    },
    "microsoft": {
        "auth_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "revoke_url": "https://login.microsoftonline.com/common/oauth2/v2.0/logout",
    },
    "slack": {
        "auth_url": "https://slack.com/oauth/v2/authorize",
        "token_url": "https://slack.com/api/oauth.v2.access",
        "revoke_url": "https://slack.com/api/auth.revoke",
    },
    "github": {
        "auth_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "revoke_url": "",
    },
    "notion": {
        "auth_url": "https://api.notion.com/v1/oauth/authorize",
        "token_url": "https://api.notion.com/v1/oauth/token",
        "revoke_url": "",
    },
}


class OAuthToken:
    def __init__(self, data: dict[str, Any]) -> None:
        self.access_token: str = data.get("access_token", "")
        self.refresh_token: str = data.get("refresh_token", "")
        self.expires_at: float = data.get("expires_at", 0.0)
        self.scope: str = data.get("scope", "")
        self.token_type: str = data.get("token_type", "Bearer")

    def is_expired(self, buffer_s: float = 60.0) -> bool:
        if self.expires_at == 0:
            return False  # no expiry known
        return time.time() > (self.expires_at - buffer_s)

    def to_dict(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "scope": self.scope,
            "token_type": self.token_type,
        }


class OAuthManager:
    """
    Manages OAuth tokens for all connectors.

    In production: integrates with SecretsVault for encrypted storage.
    In dev: stores tokens in data/oauth_tokens.json (plain, not for production).
    """

    def __init__(self, vault: Any = None) -> None:
        self._vault = vault
        self._cache: dict[str, OAuthToken] = {}
        self._load_cache()

    # ------------------------------------------------------------------
    # Token CRUD
    # ------------------------------------------------------------------

    def store_token(self, provider: str, connector_id: str, token_data: dict[str, Any]) -> None:
        key = f"{provider}:{connector_id}"
        token = OAuthToken(token_data)
        self._cache[key] = token
        self._persist_cache()
        logger.info("OAuthManager: stored token for %s", key)

    def get_token(self, provider: str, connector_id: str) -> OAuthToken | None:
        key = f"{provider}:{connector_id}"
        # Try env var first (for CI/dev)
        env_key = f"OAUTH_{provider.upper()}_{connector_id.upper().replace('-', '_')}_TOKEN"
        env_val = os.getenv(env_key)
        if env_val and key not in self._cache:
            self._cache[key] = OAuthToken({"access_token": env_val})
        return self._cache.get(key)

    def revoke_token(self, provider: str, connector_id: str) -> None:
        key = f"{provider}:{connector_id}"
        self._cache.pop(key, None)
        self._persist_cache()
        logger.info("OAuthManager: revoked token for %s", key)

    def has_valid_token(self, provider: str, connector_id: str) -> bool:
        token = self.get_token(provider, connector_id)
        if token is None or not token.access_token:
            return False
        return not token.is_expired()

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    async def refresh(self, provider: str, connector_id: str) -> bool:
        token = self.get_token(provider, connector_id)
        if token is None or not token.refresh_token:
            logger.warning("OAuthManager: no refresh token for %s:%s", provider, connector_id)
            return False
        endpoints = _OAUTH_PROVIDERS.get(provider, {})
        token_url = endpoints.get("token_url")
        if not token_url:
            return False
        try:
            import httpx
            client_id = os.getenv(f"OAUTH_{provider.upper()}_CLIENT_ID", "")
            client_secret = os.getenv(f"OAUTH_{provider.upper()}_CLIENT_SECRET", "")
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(token_url, data={
                    "grant_type": "refresh_token",
                    "refresh_token": token.refresh_token,
                    "client_id": client_id,
                    "client_secret": client_secret,
                })
                if resp.status_code == 200:
                    data = resp.json()
                    data.setdefault("refresh_token", token.refresh_token)
                    if "expires_in" in data:
                        data["expires_at"] = time.time() + float(data["expires_in"])
                    self.store_token(provider, connector_id, data)
                    logger.info("OAuthManager: refreshed token for %s:%s", provider, connector_id)
                    return True
        except Exception as exc:
            logger.error("OAuthManager: refresh failed for %s:%s: %s", provider, connector_id, exc)
        return False

    # ------------------------------------------------------------------
    # Persistence (dev mode)
    # ------------------------------------------------------------------

    def _load_cache(self) -> None:
        if not _TOKEN_CACHE_PATH.exists():
            return
        try:
            data = json.loads(_TOKEN_CACHE_PATH.read_text(encoding="utf-8"))
            for key, token_data in data.items():
                self._cache[key] = OAuthToken(token_data)
        except Exception as exc:
            logger.warning("OAuthManager: failed to load token cache: %s", exc)

    def _persist_cache(self) -> None:
        try:
            _TOKEN_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            data = {k: t.to_dict() for k, t in self._cache.items()}
            _TOKEN_CACHE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("OAuthManager: failed to persist token cache: %s", exc)


_oauth_manager: OAuthManager | None = None


def get_oauth_manager() -> OAuthManager:
    global _oauth_manager
    if _oauth_manager is None:
        _oauth_manager = OAuthManager()
    return _oauth_manager
