"""
Analytics integration — GA4 Measurement Protocol v2 + Plausible Events API.

Supports both backends (configured via credentials):
  - GA4: measurement_id, api_secret → posts to GA4 Measurement Protocol
  - Plausible: domain, api_key, site_id → posts to Plausible Events API

Out-of-the-box (no credentials): events are queued locally in
data/memory/analytics_queue.json and flushed when credentials are set.
"""
from __future__ import annotations

import json
import logging
import pathlib
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from sovereign.integrations.base_integration import (
    BaseIntegration,
    IntegrationConfig,
    IntegrationStatus,
)

logger = logging.getLogger(__name__)

_QUEUE_PATH = pathlib.Path("data/memory/analytics_queue.json")
_GA4_ENDPOINT = "https://www.google-analytics.com/mp/collect"
_PLAUSIBLE_ENDPOINT = "https://plausible.io/api/event"


def _load_queue() -> list[dict]:
    if not _QUEUE_PATH.exists():
        return []
    try:
        return json.loads(_QUEUE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_queue(q: list[dict]) -> None:
    _QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _QUEUE_PATH.write_text(json.dumps(q, indent=2, ensure_ascii=False), encoding="utf-8")


class AnalyticsIntegration(BaseIntegration):
    """
    Dual-backend analytics connector.

    Credentials dict (via IntegrationConfig.credentials):
      GA4:
        ga4_measurement_id  — e.g. "G-XXXXXXXXXX"
        ga4_api_secret      — from GA4 Data Streams > Measurement Protocol API secrets
        ga4_client_id       — stable pseudonymous ID (default: auto-generated)
      Plausible:
        plausible_domain    — domain registered in Plausible (e.g. "example.com")
        plausible_api_key   — Bearer token from account settings
      Common:
        backend             — "ga4" | "plausible" | "both" (default "both")
    """

    integration_id = "analytics"
    name = "Analytics Integration"

    def __init__(self) -> None:
        super().__init__()
        self._ga4_mid: str = ""
        self._ga4_secret: str = ""
        self._ga4_client_id: str = ""
        self._plausible_domain: str = ""
        self._plausible_api_key: str = ""
        self._backend: str = "both"
        self._http: httpx.Client | None = None
        self._session_stats: dict[str, int] = {"sent": 0, "queued": 0, "errors": 0}

    # ------------------------------------------------------------------
    # BaseIntegration
    # ------------------------------------------------------------------

    def connect(self, config: IntegrationConfig) -> bool:
        creds = config.credentials or {}
        self._ga4_mid        = creds.get("ga4_measurement_id", "")
        self._ga4_secret     = creds.get("ga4_api_secret", "")
        self._ga4_client_id  = creds.get("ga4_client_id", str(uuid.uuid4()))
        self._plausible_domain  = creds.get("plausible_domain", "")
        self._plausible_api_key = creds.get("plausible_api_key", "")
        self._backend = creds.get("backend", "both")
        self._http = httpx.Client(timeout=10.0)
        self._status = IntegrationStatus.CONNECTED
        logger.info(
            "analytics.connect: GA4=%s Plausible=%s backend=%s",
            bool(self._ga4_mid), bool(self._plausible_domain), self._backend,
        )
        self._flush_queue()
        return True

    def disconnect(self) -> bool:
        if self._http:
            self._http.close()
            self._http = None
        self._status = IntegrationStatus.DISCONNECTED
        return True

    def test_connection(self) -> bool:
        if not self._http:
            return False
        has_ga4       = bool(self._ga4_mid and self._ga4_secret)
        has_plausible = bool(self._plausible_domain and self._plausible_api_key)
        return has_ga4 or has_plausible

    def fetch(self, resource: str, params: dict) -> dict:
        if resource == "stats":
            return {"session_stats": self._session_stats}
        if resource == "queue":
            return {"queued": _load_queue()}
        return {}

    def push(self, resource: str, data: dict) -> dict:
        if resource == "event":
            ok = self.track_event(
                data.get("name", "custom_event"),
                data.get("params", {}),
                data.get("user_id", ""),
            )
            return {"sent": ok}
        return {}

    # ------------------------------------------------------------------
    # Analytics API
    # ------------------------------------------------------------------

    def track_event(
        self,
        event_name: str,
        params: dict[str, Any] | None = None,
        user_id: str = "",
        page_path: str = "/sovereign",
    ) -> bool:
        """Send a custom event. Falls back to local queue if not connected."""
        params = params or {}
        if self._status != IntegrationStatus.CONNECTED or not self._http:
            self._enqueue(event_name, params, user_id, page_path)
            return False

        success = False
        use_ga4       = self._backend in ("ga4",       "both") and self._ga4_mid
        use_plausible = self._backend in ("plausible", "both") and self._plausible_domain

        if use_ga4:
            success |= self._send_ga4(event_name, params, user_id)
        if use_plausible:
            success |= self._send_plausible(event_name, params, page_path)

        if success:
            self._session_stats["sent"] += 1
        else:
            self._enqueue(event_name, params, user_id, page_path)
        return success

    def track_session(self, mode: str, tokens: int, latency_ms: float) -> bool:
        return self.track_event("sovereign_session", {
            "operating_mode": mode,
            "tokens_used": tokens,
            "latency_ms": round(latency_ms),
        })

    def track_agent_run(self, agent_id: str, status: str, confidence: float) -> bool:
        return self.track_event("agent_run", {
            "agent_id": agent_id,
            "status": status,
            "confidence": round(confidence, 3),
        })

    def track_page_view(self, page: str, referrer: str = "") -> bool:
        return self.track_event("page_view", {"page": page, "referrer": referrer})

    def get_stats(self) -> dict:
        return {
            **self._session_stats,
            "backend": self._backend,
            "ga4_configured": bool(self._ga4_mid),
            "plausible_configured": bool(self._plausible_domain),
            "queue_length": len(_load_queue()),
        }

    # ------------------------------------------------------------------
    # GA4 Measurement Protocol v2
    # ------------------------------------------------------------------

    def _send_ga4(self, event_name: str, params: dict, user_id: str) -> bool:
        url = (
            f"{_GA4_ENDPOINT}"
            f"?measurement_id={self._ga4_mid}"
            f"&api_secret={self._ga4_secret}"
        )
        payload: dict[str, Any] = {
            "client_id": self._ga4_client_id,
            "timestamp_micros": int(time.time() * 1_000_000),
            "events": [{"name": event_name, "params": {**params, "engagement_time_msec": "100"}}],
        }
        if user_id:
            payload["user_id"] = user_id
        try:
            resp = self._http.post(url, json=payload)  # type: ignore[union-attr]
            if resp.status_code in (200, 204):
                logger.debug("analytics.ga4: sent '%s'", event_name)
                return True
            logger.warning("analytics.ga4: HTTP %d for '%s'", resp.status_code, event_name)
            return False
        except Exception as exc:
            logger.warning("analytics.ga4: %s", exc)
            self._session_stats["errors"] += 1
            return False

    # ------------------------------------------------------------------
    # Plausible Events API
    # ------------------------------------------------------------------

    def _send_plausible(self, event_name: str, params: dict, page_path: str) -> bool:
        headers = {
            "Authorization": f"Bearer {self._plausible_api_key}",
            "Content-Type": "application/json",
            "User-Agent": "SOVEREIGN-AI-OS/2.0",
        }
        payload = {
            "domain": self._plausible_domain,
            "name": event_name,
            "url": f"app://sovereign{page_path}",
            "props": {k: str(v) for k, v in params.items()},
        }
        try:
            resp = self._http.post(  # type: ignore[union-attr]
                _PLAUSIBLE_ENDPOINT, json=payload, headers=headers
            )
            if resp.status_code in (200, 202):
                logger.debug("analytics.plausible: sent '%s'", event_name)
                return True
            logger.warning("analytics.plausible: HTTP %d for '%s'", resp.status_code, event_name)
            return False
        except Exception as exc:
            logger.warning("analytics.plausible: %s", exc)
            self._session_stats["errors"] += 1
            return False

    # ------------------------------------------------------------------
    # Local queue (offline buffer)
    # ------------------------------------------------------------------

    def _enqueue(self, event_name: str, params: dict, user_id: str, page_path: str) -> None:
        q = _load_queue()
        q.append({
            "event_name": event_name,
            "params": params,
            "user_id": user_id,
            "page_path": page_path,
            "queued_at": datetime.now(timezone.utc).isoformat(),
        })
        _save_queue(q)
        self._session_stats["queued"] += 1

    def _flush_queue(self) -> int:
        q = _load_queue()
        if not q:
            return 0
        flushed, remaining = 0, []
        for item in q:
            ok = self._send_ga4(item["event_name"], item["params"], item.get("user_id", "")) \
                 or self._send_plausible(
                     item["event_name"], item["params"], item.get("page_path", "/sovereign")
                 )
            if ok:
                flushed += 1
            else:
                remaining.append(item)
        _save_queue(remaining)
        if flushed:
            logger.info("analytics: flushed %d queued events (%d remaining)", flushed, len(remaining))
        return flushed
