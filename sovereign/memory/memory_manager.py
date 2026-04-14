"""
Unified memory gateway for the SOVEREIGN AI OS.

Provides a single interface across all 14 memory domains with four access patterns:
  - direct:   key-based lookup/write
  - semantic: embedding-based search (stub — replace with vector DB)
  - graph:    relationship traversal via networkx
  - temporal: time-windowed retrieval
"""
from __future__ import annotations

import logging
import pathlib
from typing import Any

logger = logging.getLogger(__name__)

MEMORY_DOMAINS = [
    "identity",
    "operational",
    "project",
    "relationship",
    "financial",
    "learning",
    "inventory",
    "health_routine",
    "diary",
    "legal_compliance",
    "decision",
    "research",
    "content",
    "brand",
]


class MemoryManager:
    """
    Unified interface to all 14 memory domains.

    All domains share the same key/value storage contract.
    The actual backend is a JSON file per domain under data_dir/memory/.
    Replace with a proper vector + graph database for production use.
    """

    def __init__(self, data_dir: str | pathlib.Path = "data") -> None:
        self._root = pathlib.Path(data_dir) / "memory"
        self._root.mkdir(parents=True, exist_ok=True)
        # Lazy-loaded in-memory caches per domain
        self._caches: dict[str, dict[str, Any]] = {d: {} for d in MEMORY_DOMAINS}
        self._loaded: set[str] = set()

    # ------------------------------------------------------------------
    # Direct access
    # ------------------------------------------------------------------

    async def read(self, domain: str, key: str) -> dict[str, Any] | None:
        """Direct key-based lookup. Returns None if key does not exist."""
        self._ensure_domain(domain)
        await self._load(domain)
        return self._caches[domain].get(key)

    async def write(self, domain: str, key: str, value: dict[str, Any]) -> None:
        """Write a record to a domain. Creates or overwrites."""
        self._ensure_domain(domain)
        await self._load(domain)
        self._caches[domain][key] = value
        await self._persist(domain)
        logger.debug("Memory write", domain=domain, key=key)

    async def delete(self, domain: str, key: str) -> bool:
        """Delete a key. Returns True if key existed."""
        self._ensure_domain(domain)
        await self._load(domain)
        existed = key in self._caches[domain]
        self._caches[domain].pop(key, None)
        if existed:
            await self._persist(domain)
        return existed

    async def list_keys(self, domain: str) -> list[str]:
        """Return all keys in a domain."""
        self._ensure_domain(domain)
        await self._load(domain)
        return list(self._caches[domain])

    # ------------------------------------------------------------------
    # Semantic search (stub)
    # ------------------------------------------------------------------

    async def semantic_search(
        self,
        query: str,
        domain: str | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Embedding-based semantic search across one or all domains.

        Stub: performs simple substring matching on string values.
        Replace with a real vector index (Chroma, Qdrant, Pinecone, etc.)
        for production use.
        """
        domains = [domain] if domain else MEMORY_DOMAINS
        results: list[dict[str, Any]] = []
        query_lower = query.lower()

        for d in domains:
            try:
                await self._load(d)
                for key, value in self._caches[d].items():
                    if self._matches(query_lower, value):
                        results.append(
                            {"domain": d, "key": key, "record": value, "score": 1.0}
                        )
            except Exception:
                pass

        return results[:top_k]

    # ------------------------------------------------------------------
    # Graph traversal (stub)
    # ------------------------------------------------------------------

    async def graph_traverse(
        self,
        start_key: str,
        relationship: str,
        depth: int = 2,
    ) -> list[dict[str, Any]]:
        """
        Traverse memory as a graph via named relationships.

        Stub: returns an empty list.
        Replace with a real graph database (Neo4j, networkx + persistence).
        """
        logger.debug(
            "Graph traverse (stub)",
            start=start_key,
            rel=relationship,
            depth=depth,
        )
        return []

    # ------------------------------------------------------------------
    # Temporal recall (stub)
    # ------------------------------------------------------------------

    async def temporal_recall(
        self,
        domain: str,
        since_iso: str,
        until_iso: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve records from a domain within a time window.

        Filters on record["updated_at"] or record["created_at"] if present.
        Stub: returns all records — replace with proper timestamp indexing.
        """
        self._ensure_domain(domain)
        await self._load(domain)
        # Stub: return all records (no timestamp filtering yet)
        return [
            {"key": k, "record": v}
            for k, v in self._caches[domain].items()
        ]

    # ------------------------------------------------------------------
    # Snapshot (for prompt injection)
    # ------------------------------------------------------------------

    async def get_snapshot(
        self,
        domains: list[str] | None = None,
        max_records_per_domain: int = 5,
    ) -> dict[str, Any]:
        """
        Return a compact snapshot of relevant memory for injection into prompts.

        Used by PromptBuilder to build the dynamic section.
        Returns at most max_records_per_domain records per domain.
        """
        target_domains = domains or MEMORY_DOMAINS
        snapshot: dict[str, Any] = {}

        for d in target_domains:
            try:
                await self._load(d)
                records = dict(
                    list(self._caches[d].items())[:max_records_per_domain]
                )
                if records:
                    snapshot[d] = records
            except Exception:
                pass

        return snapshot

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _ensure_domain(self, domain: str) -> None:
        if domain not in MEMORY_DOMAINS:
            raise ValueError(
                f"Unknown memory domain '{domain}'. "
                f"Valid domains: {MEMORY_DOMAINS}"
            )

    async def _load(self, domain: str) -> None:
        """Load domain from disk into cache (once per session)."""
        if domain in self._loaded:
            return
        import json
        path = self._root / f"{domain}.json"
        if path.exists():
            try:
                self._caches[domain] = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning("Failed to load memory domain", domain=domain, error=str(exc))
                self._caches[domain] = {}
        self._loaded.add(domain)

    async def _persist(self, domain: str) -> None:
        """Persist domain cache to disk."""
        import json
        path = self._root / f"{domain}.json"
        path.write_text(
            json.dumps(self._caches[domain], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @staticmethod
    def _matches(query: str, value: Any) -> bool:
        """Simple substring matching on any string values in a record."""
        if isinstance(value, str):
            return query in value.lower()
        if isinstance(value, dict):
            return any(
                query in str(v).lower()
                for v in value.values()
            )
        return query in str(value).lower()
