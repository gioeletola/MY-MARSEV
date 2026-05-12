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

from sovereign.memory.access_patterns.semantic import SemanticIndex

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
    "business_idea",
    "personal_constitution",
    "personal_version",
    "next_action",
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
        # Lazy semantic indexes per domain; invalidated on write
        self._semantic_indexes: dict[str, SemanticIndex] = {}

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
        # Invalidate the cached semantic index so it is rebuilt on next search
        self._semantic_indexes.pop(domain, None)
        logger.debug("Memory write", domain=domain, key=key)

    async def delete(self, domain: str, key: str) -> bool:
        """Delete a key. Returns True if key existed."""
        self._ensure_domain(domain)
        await self._load(domain)
        existed = key in self._caches[domain]
        self._caches[domain].pop(key, None)
        if existed:
            await self._persist(domain)
            # Invalidate semantic index
            self._semantic_indexes.pop(domain, None)
        return existed

    async def list_keys(self, domain: str) -> list[str]:
        """Return all keys in a domain."""
        self._ensure_domain(domain)
        await self._load(domain)
        return list(self._caches[domain])

    # ------------------------------------------------------------------
    # Semantic search — vector embeddings with TF-IDF fallback
    # ------------------------------------------------------------------

    async def semantic_search(
        self,
        query: str,
        domain: str | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Embedding-based cosine similarity search across one or all memory domains.

        Uses SemanticIndex (sentence-transformers if available, otherwise enhanced
        TF-IDF with character + word n-grams).  Indexes are built lazily per
        domain and cached in self._semantic_indexes; they are invalidated whenever
        a domain is written to.

        Returns a list of dicts: [{"key": str, "score": float, "value": Any}].
        The "domain" key is also included when searching across multiple domains.
        """
        domains_to_search = [domain] if domain else MEMORY_DOMAINS

        if domain:
            # Single-domain search — use (or build) the per-domain index
            self._ensure_domain(domain)
            await self._load(domain)
            index = await self._get_semantic_index(domain)
            hits = index.search(query, top_k=top_k)
            results: list[dict[str, Any]] = []
            for key, score in hits:
                value = self._caches[domain].get(key)
                results.append({"key": key, "score": score, "value": value})
            return results

        # Multi-domain search: gather all docs, build a combined index
        docs: list[tuple[str, str, Any]] = []  # (domain, key, value)
        for d in domains_to_search:
            try:
                await self._load(d)
                for key, value in self._caches[d].items():
                    docs.append((d, key, value))
            except Exception:
                pass

        if not docs:
            return []

        # Build a transient index over all docs
        key_text: dict[str, str] = {}
        # Use "domain::key" as the composite key to avoid collisions
        composite_keys = []
        for d, key, value in docs:
            ck = f"{d}::{key}"
            key_text[ck] = self._record_to_text(value)
            composite_keys.append(ck)

        # Use a unique collection name so this transient index never pollutes
        # the persistent ChromaDB state shared across sessions and test runs.
        import uuid as _uuid
        index = SemanticIndex(collection=f"_transient_{_uuid.uuid4().hex[:8]}")
        index.build(key_text)
        hits = index.search(query, top_k=top_k)

        results = []
        # Map composite key back to domain/key/value
        ck_to_doc = {f"{d}::{key}": (d, key, value) for d, key, value in docs}
        for ck, score in hits:
            d, key, value = ck_to_doc[ck]
            results.append({"domain": d, "key": key, "score": score, "value": value})
        return results

    async def rebuild_semantic_index(self, domain: str) -> SemanticIndex:
        """
        Force-rebuild the semantic index for *domain* and cache it.

        Useful after bulk writes or external data changes.
        """
        self._ensure_domain(domain)
        await self._load(domain)
        self._semantic_indexes.pop(domain, None)
        return await self._get_semantic_index(domain)

    async def _get_semantic_index(self, domain: str) -> SemanticIndex:
        """Return the cached SemanticIndex for *domain*, building it if needed."""
        if domain not in self._semantic_indexes:
            key_text = {
                key: self._record_to_text(value)
                for key, value in self._caches[domain].items()
            }
            index = SemanticIndex()
            index.build(key_text)
            self._semantic_indexes[domain] = index
            logger.debug(
                "Built semantic index for domain=%s mode=%s size=%d",
                domain, index.mode, len(index),
            )
        return self._semantic_indexes[domain]

    @staticmethod
    def _record_to_text(record: Any) -> str:
        """Flatten a record to a single searchable string."""
        if isinstance(record, str):
            return record
        if isinstance(record, dict):
            return " ".join(str(v) for v in record.values())
        return str(record)

    # ------------------------------------------------------------------
    # Graph traversal via networkx
    # ------------------------------------------------------------------

    async def graph_traverse(
        self,
        start_key: str,
        relationship: str,
        depth: int = 2,
    ) -> list[dict[str, Any]]:
        """
        Traverse memory as a graph via named relationship edges.

        Builds an in-memory networkx DiGraph from all loaded domain caches
        where any record that references another key via `relationship` field
        forms an edge.  BFS up to `depth` hops from `start_key`.
        """
        try:
            import networkx as nx  # type: ignore[import]
        except ImportError:
            logger.warning("networkx not installed — graph_traverse unavailable")
            return []

        # Load all domains
        for domain in MEMORY_DOMAINS:
            await self._load(domain)

        G: nx.DiGraph = nx.DiGraph()
        # Add nodes + edges from all cached records
        for domain, cache in self._caches.items():
            for key, record in cache.items():
                node_id = f"{domain}:{key}"
                G.add_node(node_id, domain=domain, key=key, record=record)
                if isinstance(record, dict):
                    targets = record.get(relationship, [])
                    if isinstance(targets, str):
                        targets = [targets]
                    for target in targets:
                        G.add_edge(node_id, target)

        if start_key not in G:
            # Try prefix-less lookup
            candidates = [n for n in G.nodes if n.endswith(f":{start_key}") or n == start_key]
            if not candidates:
                return []
            start_key = candidates[0]

        visited: list[dict[str, Any]] = []
        for node in nx.bfs_tree(G, start_key, depth_limit=depth).nodes:
            if node == start_key:
                continue
            node_data = G.nodes[node]
            visited.append({
                "node": node,
                "domain": node_data.get("domain"),
                "key": node_data.get("key"),
                "record": node_data.get("record"),
            })

        logger.debug("graph_traverse: %d nodes from %s rel=%s depth=%d",
                     len(visited), start_key, relationship, depth)
        return visited

    # ------------------------------------------------------------------
    # Temporal recall with timestamp filtering
    # ------------------------------------------------------------------

    async def temporal_recall(
        self,
        domain: str,
        since_iso: str,
        until_iso: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve records from a domain within a time window.

        Filters on record["updated_at"] falling back to record["created_at"].
        ISO-8601 strings are compared lexicographically (valid for UTC timestamps).
        """
        self._ensure_domain(domain)
        await self._load(domain)

        results: list[dict[str, Any]] = []
        for key, record in self._caches[domain].items():
            if not isinstance(record, dict):
                continue
            ts = record.get("updated_at") or record.get("created_at") or ""
            if not ts:
                continue
            if ts < since_iso:
                continue
            if until_iso and ts > until_iso:
                continue
            results.append({"key": key, "record": record, "timestamp": ts})

        results.sort(key=lambda r: r["timestamp"])
        logger.debug("temporal_recall: domain=%s since=%s until=%s → %d records",
                     domain, since_iso, until_iso, len(results))
        return results

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
        """Persist domain cache to disk atomically."""
        from sovereign.memory._atomic_io import _save_json
        path = self._root / f"{domain}.json"
        _save_json(path, self._caches[domain], ensure_ascii=False)

