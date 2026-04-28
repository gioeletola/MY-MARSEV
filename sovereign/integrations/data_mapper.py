"""DataMapper — normalize connector-specific data formats to memory records."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_SCHEMA_REGISTRY: dict[str, dict[str, list[str]]] = {
    "binance":    {"required": ["symbol", "price"], "optional": ["volume", "change_pct", "timestamp"]},
    "stripe":     {"required": ["amount", "currency"], "optional": ["customer_id", "status", "description"]},
    "telegram":   {"required": ["chat_id", "text"], "optional": ["from_user", "date", "message_id"]},
    "slack":      {"required": ["channel", "text"], "optional": ["user", "ts", "thread_ts"]},
    "github":     {"required": ["repo", "event_type"], "optional": ["actor", "ref", "sha", "url"]},
    "notion":     {"required": ["page_id", "title"], "optional": ["properties", "url", "last_edited"]},
    "linear":     {"required": ["issue_id", "title"], "optional": ["state", "assignee", "priority", "labels"]},
    "rss":        {"required": ["title", "url"], "optional": ["summary", "published", "author", "tags"]},
    "weather":    {"required": ["location", "temp_c"], "optional": ["humidity", "conditions", "wind_kmh"]},
    "coingecko":  {"required": ["coin_id", "price_usd"], "optional": ["market_cap", "volume_24h", "change_24h"]},
    "strava":     {"required": ["activity_id", "type"], "optional": ["distance_km", "duration_s", "elevation_m"]},
    "spotify":    {"required": ["track_id", "name"], "optional": ["artist", "album", "duration_ms", "popularity"]},
}


class DataMapper:
    """Normalize data from different connector formats to a canonical memory record."""

    def normalize(self, connector_id: str, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Apply connector-specific normalization and return a canonical dict."""
        method_name = f"_normalize_{connector_id.replace('-', '_')}"
        normalizer = getattr(self, method_name, None)
        if normalizer:
            try:
                return normalizer(raw_data)
            except Exception as exc:
                logger.warning("DataMapper: normalization failed for %s: %s", connector_id, exc)

        # Generic normalization: validate required fields, add metadata
        schema = _SCHEMA_REGISTRY.get(connector_id, {})
        result = {
            "_connector": connector_id,
            "_normalized_at": datetime.now(timezone.utc).isoformat(),
            **raw_data,
        }
        missing = [f for f in schema.get("required", []) if f not in raw_data]
        if missing:
            logger.warning("DataMapper: %s data missing required fields: %s", connector_id, missing)
            result["_validation_warnings"] = [f"Missing: {m}" for m in missing]
        return result

    def to_memory_record(self, normalized: dict[str, Any]) -> dict[str, Any]:
        """Convert a normalized connector dict to a memory domain record."""
        connector = normalized.get("_connector", "unknown")
        now = datetime.now(timezone.utc).isoformat()
        return {
            "source": connector,
            "data": {k: v for k, v in normalized.items() if not k.startswith("_")},
            "created_at": now,
            "updated_at": now,
            "tags": [connector],
        }

    def validate(self, connector_id: str, data: dict[str, Any]) -> list[str]:
        """Return list of validation errors for the given connector data."""
        schema = _SCHEMA_REGISTRY.get(connector_id, {})
        return [f"Missing required field: {f}" for f in schema.get("required", []) if f not in data]

    # ------------------------------------------------------------------
    # Per-connector normalizers
    # ------------------------------------------------------------------

    def _normalize_binance(self, data: dict) -> dict:
        return {
            "_connector": "binance",
            "_normalized_at": datetime.now(timezone.utc).isoformat(),
            "symbol":     data.get("symbol", data.get("s", "")),
            "price":      float(data.get("price", data.get("p", data.get("c", 0)))),
            "volume":     float(data.get("volume", data.get("v", 0))),
            "change_pct": float(data.get("priceChangePercent", data.get("P", 0))),
            "timestamp":  data.get("closeTime", data.get("T", "")),
        }

    def _normalize_stripe(self, data: dict) -> dict:
        return {
            "_connector": "stripe",
            "_normalized_at": datetime.now(timezone.utc).isoformat(),
            "amount":      int(data.get("amount", 0)) / 100,  # cents → units
            "currency":    data.get("currency", "usd").upper(),
            "customer_id": data.get("customer", ""),
            "status":      data.get("status", ""),
            "description": data.get("description", ""),
            "payment_id":  data.get("id", ""),
        }

    def _normalize_github(self, data: dict) -> dict:
        repo = data.get("repository", {})
        actor = data.get("sender", data.get("pusher", {}))
        return {
            "_connector": "github",
            "_normalized_at": datetime.now(timezone.utc).isoformat(),
            "repo":       repo.get("full_name", data.get("repo", "")),
            "event_type": data.get("action", data.get("event_type", "")),
            "actor":      actor.get("login", "") if isinstance(actor, dict) else str(actor),
            "ref":        data.get("ref", ""),
            "sha":        data.get("after", data.get("sha", "")),
            "url":        repo.get("html_url", ""),
        }

    def _normalize_weather(self, data: dict) -> dict:
        main = data.get("main", data)
        return {
            "_connector": "weather",
            "_normalized_at": datetime.now(timezone.utc).isoformat(),
            "location":   data.get("name", data.get("location", "")),
            "temp_c":     float(main.get("temp", data.get("temp_c", 0))),
            "humidity":   float(main.get("humidity", data.get("humidity", 0))),
            "conditions": (data.get("weather", [{}])[0].get("description", data.get("conditions", ""))),
        }
