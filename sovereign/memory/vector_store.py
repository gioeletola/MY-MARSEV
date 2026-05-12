"""Persistent vector store — ChromaDB + sentence-transformers with TF-IDF fallback."""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    import chromadb  # type: ignore[import]
    _CHROMADB_AVAILABLE = True
except ImportError:
    chromadb = None  # type: ignore[assignment]
    _CHROMADB_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer as _SentenceTransformer  # type: ignore[import]
    _ST_AVAILABLE = True
except ImportError:
    _SentenceTransformer = None  # type: ignore[assignment,misc]
    _ST_AVAILABLE = False


class VectorStore:
    """ChromaDB-backed persistent vector store with sentence-transformers embeddings."""

    def __init__(
        self,
        persist_dir: str | Path = "data/vector_store",
        collection: str = "sovereign_memory",
    ) -> None:
        self._available: bool = False
        self._st_model: Any = None
        self._collection: Any = None
        self._backend: str = "unavailable"

        if not _CHROMADB_AVAILABLE:
            logger.debug("chromadb not installed — VectorStore unavailable")
            return

        try:
            client = chromadb.PersistentClient(path=str(persist_dir))
            self._collection = client.get_or_create_collection(name=collection)
            self._available = True
        except Exception as exc:
            logger.warning("ChromaDB init failed: %s", exc)
            return

        if _ST_AVAILABLE and _SentenceTransformer is not None:
            try:
                self._st_model = _SentenceTransformer("all-MiniLM-L6-v2")
                self._backend = "chromadb+sentence-transformers"
                logger.info("VectorStore: backend=chromadb+sentence-transformers")
            except Exception as exc:
                logger.warning("SentenceTransformer load failed: %s — using hash embeddings", exc)
                self._backend = "chromadb"
                logger.info("VectorStore: backend=chromadb (hash embeddings)")
        else:
            self._backend = "chromadb"
            logger.info("VectorStore: backend=chromadb (hash embeddings)")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _embed(self, text: str) -> list[float]:
        if self._st_model is not None:
            return self._st_model.encode([text], show_progress_bar=False, convert_to_numpy=True)[0].tolist()
        digest = hashlib.sha256(text.encode()).digest()
        vec = [((b / 255.0) * 2.0 - 1.0) for b in digest]
        return vec

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def upsert(self, doc_id: str, text: str, metadata: dict[str, Any] | None = None) -> None:
        if not self._available or self._collection is None:
            return
        try:
            embedding = self._embed(text)
            self._collection.upsert(
                ids=[doc_id],
                documents=[text],
                embeddings=[embedding],
                metadatas=[metadata or {}],
            )
        except Exception as exc:
            logger.error("VectorStore.upsert failed for id=%s: %s", doc_id, exc)

    def search(
        self,
        query: str,
        n_results: int = 10,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if not self._available or self._collection is None:
            return []
        try:
            count = self._collection.count()
            if count == 0:
                return []
            actual_n = min(n_results, count)
            kwargs: dict[str, Any] = {
                "query_embeddings": [self._embed(query)],
                "n_results": actual_n,
            }
            if where:
                kwargs["where"] = where
            result = self._collection.query(**kwargs)
            items: list[dict[str, Any]] = []
            ids = result.get("ids", [[]])[0]
            docs = result.get("documents", [[]])[0]
            distances = result.get("distances", [[]])[0]
            metadatas = result.get("metadatas", [[]])[0]
            for doc_id, text, dist, meta in zip(ids, docs, distances, metadatas):
                items.append({
                    "id": doc_id,
                    "text": text,
                    "score": float(1.0 - dist),
                    "metadata": meta or {},
                })
            return items
        except Exception as exc:
            logger.error("VectorStore.search failed: %s", exc)
            return []

    def delete(self, doc_id: str) -> None:
        if not self._available or self._collection is None:
            return
        try:
            self._collection.delete(ids=[doc_id])
        except Exception as exc:
            logger.error("VectorStore.delete failed for id=%s: %s", doc_id, exc)

    def count(self) -> int:
        if not self._available or self._collection is None:
            return 0
        try:
            return int(self._collection.count())
        except Exception:
            return 0

    @property
    def available(self) -> bool:
        return self._available

    @property
    def backend(self) -> str:
        return self._backend
