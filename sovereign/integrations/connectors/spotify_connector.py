"""Spotify connector — playlists, recently played, top tracks, listening stats."""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

from .connector_base import ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult

logger = logging.getLogger("connector.spotify")
_BASE = "https://api.spotify.com/v1"


class SpotifyConnector(ConnectorBase):
    connector_id = "spotify"
    connector_name = "Spotify"
    connector_description = "Spotify Web API — playback, playlists, top tracks, listening stats."
    connector_status = ConnectorStatus.CONNECTED
    requires_oauth = True
    required_scopes = ["user-read-currently-playing", "user-top-read",
                       "user-read-recently-played", "playlist-modify-public"]

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._token = os.environ.get("SPOTIFY_ACCESS_TOKEN", "")
        self._client_id = os.environ.get("SPOTIFY_CLIENT_ID", "")
        self._client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
        self._refresh_token = os.environ.get("SPOTIFY_REFRESH_TOKEN", "")
        self._data: dict[str, Any] = {}
        self._error_count = 0

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"}

    async def _refresh(self) -> bool:
        """Refresh access token via refresh token."""
        if not self._refresh_token or not self._client_id or not self._client_secret:
            return False
        try:
            import base64
            creds = base64.b64encode(f"{self._client_id}:{self._client_secret}".encode()).decode()
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.post("https://accounts.spotify.com/api/token",
                                 data={"grant_type": "refresh_token", "refresh_token": self._refresh_token},
                                 headers={"Authorization": f"Basic {creds}"})
                r.raise_for_status()
                self._token = r.json()["access_token"]
                return True
        except Exception:
            return False

    async def connect(self) -> bool:
        if not self._token:
            if not await self._refresh():
                self._last_error = "SPOTIFY_ACCESS_TOKEN or SPOTIFY_REFRESH_TOKEN required"
                return False
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{_BASE}/me", headers=self._headers())
                r.raise_for_status()
                self._data["profile"] = r.json()
                return True
        except Exception as exc:
            self._last_error = str(exc)
            self._error_count += 1
            return False

    async def disconnect(self) -> None:
        self._data = {}

    async def sync(self) -> SyncResult:
        t0 = time.monotonic()
        try:
            recent = await self.get_listening_stats()
            self._data["stats"] = recent
            self._last_sync = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
            self._records_synced = 1
            return SyncResult(self.connector_id, True, 1, duration_ms=(time.monotonic() - t0) * 1000)
        except Exception as exc:
            self._last_error = str(exc)
            self._error_count += 1
            return SyncResult(self.connector_id, False, errors=[str(exc)], duration_ms=(time.monotonic() - t0) * 1000)

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(self.connector_id, self.connector_status,
                               last_sync=self._last_sync, last_error=self._last_error,
                               records_synced=self._records_synced, metadata={"error_count": self._error_count})

    async def get_now_playing(self) -> dict[str, Any]:
        """Return the currently playing track."""
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{_BASE}/me/player/currently-playing", headers=self._headers())
                if r.status_code == 204:
                    return {"playing": False}
                r.raise_for_status()
                item = r.json().get("item", {})
                return {
                    "playing": True,
                    "track": item.get("name"),
                    "artist": ", ".join(a["name"] for a in item.get("artists", [])),
                    "album": item.get("album", {}).get("name"),
                }
        except Exception as exc:
            return {"error": str(exc)}

    async def create_focus_playlist(self, name: str = "Focus Session") -> dict[str, Any]:
        """Create a new empty playlist."""
        try:
            user_id = self._data.get("profile", {}).get("id", "")
            if not user_id:
                return {"error": "Connect first to get user ID"}
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.post(f"{_BASE}/users/{user_id}/playlists",
                                 json={"name": name, "description": "SOVEREIGN focus session"},
                                 headers={**self._headers(), "Content-Type": "application/json"})
                r.raise_for_status()
                pl = r.json()
                return {"created": True, "playlist_id": pl["id"], "url": pl["external_urls"]["spotify"]}
        except Exception as exc:
            return {"created": False, "error": str(exc)}

    async def get_listening_stats(self) -> dict[str, Any]:
        """Return top tracks and recently played summary."""
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                top_r = await c.get(f"{_BASE}/me/top/tracks", params={"limit": 10, "time_range": "short_term"},
                                    headers=self._headers())
                top_r.raise_for_status()
                top = [{"name": t["name"], "artist": t["artists"][0]["name"]} for t in top_r.json().get("items", [])]
                recent_r = await c.get(f"{_BASE}/me/player/recently-played", params={"limit": 20},
                                       headers=self._headers())
                recent_r.raise_for_status()
                recent_count = len(recent_r.json().get("items", []))
                return {"top_tracks": top, "recent_plays_fetched": recent_count}
        except Exception as exc:
            return {"error": str(exc)}
