"""
Semantic (embedding-based) memory access.

Provides three levels of semantic search:
  1. VectorStore (ChromaDB + sentence-transformers) — persistent, best quality, optional
  2. Dense embeddings via sentence-transformers (in-memory, optional)
  3. Enhanced TF-IDF with char + word n-grams (good quality, always available)
  4. Basic TF-IDF word n-grams (fallback, always available)

The public API is SemanticIndex, which wraps EmbeddingSemanticSearch and keeps
a key→text mapping for use with memory domains.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.pipeline import FeatureUnion

from sovereign.memory.vector_store import VectorStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional: sentence-transformers dense embeddings
# ---------------------------------------------------------------------------
try:
    from sentence_transformers import SentenceTransformer as _SentenceTransformer  # type: ignore[import]

    _SENTENCE_TRANSFORMER_AVAILABLE = True
    logger.debug("sentence_transformers available — dense embeddings enabled")
except ImportError:
    _SentenceTransformer = None  # type: ignore[assignment,misc]
    _SENTENCE_TRANSFORMER_AVAILABLE = False
    logger.debug("sentence_transformers not installed — using enhanced TF-IDF")


# ---------------------------------------------------------------------------
# EmbeddingSemanticSearch
# ---------------------------------------------------------------------------

class EmbeddingSemanticSearch:
    """
    Computes text embeddings and supports cosine-similarity search.

    Fallback chain:
      sentence_transformers (dense) → enhanced TF-IDF (char+word) → basic TF-IDF
    """

    _st_model: Any  # SentenceTransformer instance or None

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._texts: list[str] = []
        self._embeddings: np.ndarray | None = None
        self._vectorizer: Any = None  # TF-IDF vectorizer (fallback)
        self._tfidf_matrix: Any = None  # sparse matrix (fallback)
        self._mode: str = "none"  # "dense" | "enhanced_tfidf" | "basic_tfidf"

        if _SENTENCE_TRANSFORMER_AVAILABLE:
            try:
                self._st_model = _SentenceTransformer(model_name)
                self._mode = "dense"
                logger.info("EmbeddingSemanticSearch: mode=dense model=%s", model_name)
            except Exception as exc:
                logger.warning("Failed to load SentenceTransformer(%s): %s", model_name, exc)
                self._st_model = None
                self._mode = "enhanced_tfidf"
        else:
            self._st_model = None
            self._mode = "enhanced_tfidf"

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def fit(self, texts: list[str]) -> None:
        """Compute and store embeddings for the given corpus."""
        self._texts = list(texts)
        if not self._texts:
            self._embeddings = None
            self._tfidf_matrix = None
            return

        if self._mode == "dense":
            self._fit_dense()
        else:
            self._fit_tfidf()

    def search(self, query: str, top_k: int = 5) -> list[tuple[int, float]]:
        """
        Return top-k (index, score) tuples sorted by cosine similarity (descending).

        Score is in [0, 1].  Only results with score > 0 are returned.
        """
        if not self._texts:
            return []

        if self._mode == "dense" and self._embeddings is not None:
            return self._search_dense(query, top_k)
        if self._tfidf_matrix is not None and self._vectorizer is not None:
            return self._search_tfidf(query, top_k)
        return []

    # ------------------------------------------------------------------
    # Dense embedding implementation
    # ------------------------------------------------------------------

    def _fit_dense(self) -> None:
        self._embeddings = self._st_model.encode(
            self._texts, show_progress_bar=False, convert_to_numpy=True
        )

    def _search_dense(self, query: str, top_k: int) -> list[tuple[int, float]]:
        query_vec = self._st_model.encode([query], show_progress_bar=False, convert_to_numpy=True)
        scores = cosine_similarity(query_vec, self._embeddings)[0]
        return _rank(scores, top_k)

    # ------------------------------------------------------------------
    # Enhanced TF-IDF (char_wb n-grams + word n-grams)
    # ------------------------------------------------------------------

    def _build_vectorizer(self) -> Any:
        """Build an enhanced vectorizer using character and word n-grams."""
        try:
            char_vec = TfidfVectorizer(
                analyzer="char_wb",
                ngram_range=(3, 5),
                strip_accents="unicode",
                lowercase=True,
                max_features=8_000,
                sublinear_tf=True,
            )
            word_vec = TfidfVectorizer(
                analyzer="word",
                ngram_range=(1, 2),
                strip_accents="unicode",
                lowercase=True,
                max_features=8_000,
                sublinear_tf=True,
            )
            vectorizer = FeatureUnion(
                [("char", char_vec), ("word", word_vec)],
                transformer_weights={"char": 0.5, "word": 1.0},
            )
            self._mode = "enhanced_tfidf"
            return vectorizer
        except Exception as exc:
            logger.warning("Enhanced TF-IDF build failed (%s), falling back to basic", exc)
            self._mode = "basic_tfidf"
            return TfidfVectorizer(
                strip_accents="unicode",
                lowercase=True,
                ngram_range=(1, 2),
                max_features=10_000,
            )

    def _fit_tfidf(self) -> None:
        self._vectorizer = self._build_vectorizer()
        try:
            self._tfidf_matrix = self._vectorizer.fit_transform(self._texts)
        except Exception as exc:
            logger.error("TF-IDF fit failed: %s", exc)
            self._tfidf_matrix = None

    def _search_tfidf(self, query: str, top_k: int) -> list[tuple[int, float]]:
        try:
            query_vec = self._vectorizer.transform([query])
            scores = cosine_similarity(query_vec, self._tfidf_matrix)[0]
            return _rank(scores, top_k)
        except Exception as exc:
            logger.error("TF-IDF search failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def mode(self) -> str:
        """Current embedding mode: 'dense', 'enhanced_tfidf', or 'basic_tfidf'."""
        return self._mode

    def __len__(self) -> int:
        return len(self._texts)


# ---------------------------------------------------------------------------
# SemanticIndex — domain-level wrapper
# ---------------------------------------------------------------------------

class SemanticIndex:
    """
    Maps string keys to texts and provides semantic search over them.

    Intended for use with MemoryManager domains.  Call `build(mapping)` to
    index a key→text mapping, then `search(query)` to retrieve top results.
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        persist_dir: str = "data/vector_store",
        collection: str = "sovereign_memory",
    ) -> None:
        self._engine = EmbeddingSemanticSearch(model_name=model_name)
        self._keys: list[str] = []
        self._vector_store = VectorStore(persist_dir=persist_dir, collection=collection)

    def build(self, key_text_mapping: dict[str, str]) -> None:
        """
        Build (or rebuild) the index from a key→text mapping.

        Args:
            key_text_mapping: {key: searchable_text_for_key}
        """
        self._keys = list(key_text_mapping.keys())
        texts = [key_text_mapping[k] for k in self._keys]
        self._engine.fit(texts)

    def search(self, query: str, top_k: int = 5) -> list[tuple[str, float]]:
        """
        Search the index.

        Returns:
            List of (key, score) tuples sorted by score descending.

        VectorStore is only used when it has real semantic embeddings
        (sentence-transformers). With hash-based embeddings the cosine
        similarity is meaningless, so TF-IDF is strictly better in that case.
        """
        use_vector_store = (
            self._vector_store.available
            and self._keys
            and self._vector_store.backend == "chromadb+sentence-transformers"
        )
        if use_vector_store:
            for key in self._keys:
                text = self._get_text_for_key(key)
                if text is not None:
                    self._vector_store.upsert(key, text)
            results = self._vector_store.search(query, n_results=top_k)
            return [(r["id"], r["score"]) for r in results if r["id"] in set(self._keys)]

        hits = self._engine.search(query, top_k=top_k)
        return [(self._keys[idx], score) for idx, score in hits]

    def _get_text_for_key(self, key: str) -> str | None:
        """Return the text for a key from the engine's internal corpus."""
        try:
            idx = self._keys.index(key)
            if hasattr(self._engine, "_texts") and idx < len(self._engine._texts):
                return self._engine._texts[idx]
        except (ValueError, AttributeError):
            pass
        return None

    @property
    def mode(self) -> str:
        if self._vector_store.available:
            return self._vector_store.backend
        return self._engine.mode

    def __len__(self) -> int:
        return len(self._keys)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _rank(scores: np.ndarray, top_k: int) -> list[tuple[int, float]]:
    """Return top-k (index, score) pairs with score > 0, sorted descending."""
    ranked_idx = np.argsort(scores)[::-1]
    results: list[tuple[int, float]] = []
    for idx in ranked_idx:
        if len(results) >= top_k:
            break
        score = float(scores[idx])
        if score > 0.0:
            results.append((int(idx), round(score, 4)))
    return results
