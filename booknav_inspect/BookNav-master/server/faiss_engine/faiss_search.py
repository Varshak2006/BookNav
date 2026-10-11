"""
FAISS Vector Search Module - Core Search Service.

Manages the FAISS index lifecycle: building, loading, searching,
persisting, and updating.  Uses IndexFlatIP with L2-normalised
vectors so that inner-product scores equal cosine similarity.

An IndexIDMap wrapper maps FAISS internal row IDs to integer keys
that correspond to entries in a separate JSON mapping file which
stores the MongoDB ObjectId strings.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import faiss
import numpy as np

from . import config
from .embedding_adapter import build_document_text, encode_query, encode_texts

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def validate_vector(vec: np.ndarray, label: str = "vector") -> np.ndarray:
    """
    Validate that *vec* is a finite float32 vector of the expected
    dimension.  Returns the validated (and reshaped if needed) array.
    """
    if vec is None:
        raise ValueError(f"{label} is None.")
    if not isinstance(vec, np.ndarray):
        try:
            vec = np.asarray(vec, dtype=np.float32)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} cannot be converted to a numeric array: {exc}")

    if vec.ndim == 1:
        vec = vec.reshape(1, -1)
    if vec.ndim != 2 or vec.shape[1] != config.EMBEDDING_DIM:
        raise ValueError(
            f"{label} has shape {vec.shape}, expected (*, {config.EMBEDDING_DIM})."
        )
    if not np.all(np.isfinite(vec)):
        raise ValueError(f"{label} contains non-finite values (NaN or Inf).")
    return vec.astype(np.float32)


def _normalise(vec: np.ndarray) -> np.ndarray:
    """L2-normalise each row in-place and return the array."""
    faiss.normalize_L2(vec)
    return vec


# ---------------------------------------------------------------------------
# ID Mapping
# ---------------------------------------------------------------------------


class IDMapping:
    """
    Bidirectional mapping between integer FAISS IDs and MongoDB
    ObjectId strings.

    Persisted as a JSON file alongside the FAISS index.
    """

    def __init__(self):
        self._int_to_mongo: Dict[int, str] = {}
        self._mongo_to_int: Dict[str, int] = {}
        self._next_id: int = 0

    # -- mutators -----------------------------------------------------------

    def add(self, mongo_id: str) -> int:
        """Register a MongoDB ID and return the FAISS integer ID."""
        if mongo_id in self._mongo_to_int:
            return self._mongo_to_int[mongo_id]
        fid = self._next_id
        self._next_id += 1
        self._int_to_mongo[fid] = mongo_id
        self._mongo_to_int[mongo_id] = fid
        return fid

    def remove(self, mongo_id: str) -> Optional[int]:
        """Remove a mapping.  Returns the old FAISS ID or None."""
        fid = self._mongo_to_int.pop(mongo_id, None)
        if fid is not None:
            self._int_to_mongo.pop(fid, None)
        return fid

    def clear(self):
        self._int_to_mongo.clear()
        self._mongo_to_int.clear()
        self._next_id = 0

    # -- lookups ------------------------------------------------------------

    def mongo_id(self, faiss_id: int) -> Optional[str]:
        return self._int_to_mongo.get(faiss_id)

    def faiss_id(self, mongo_id: str) -> Optional[int]:
        return self._mongo_to_int.get(mongo_id)

    def has_mongo_id(self, mongo_id: str) -> bool:
        return mongo_id in self._mongo_to_int

    def __len__(self):
        return len(self._int_to_mongo)

    # -- persistence --------------------------------------------------------

    def save(self, path: Path):
        data = {
            "int_to_mongo": {str(k): v for k, v in self._int_to_mongo.items()},
            "next_id": self._next_id,
        }
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        shutil.move(str(tmp), str(path))
        logger.debug("ID mapping saved to %s (%d entries)", path, len(self))

    def load(self, path: Path):
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        self._int_to_mongo = {int(k): v for k, v in data["int_to_mongo"].items()}
        self._mongo_to_int = {v: int(k) for k, v in data["int_to_mongo"].items()}
        self._next_id = data.get("next_id", max(self._int_to_mongo.keys(), default=-1) + 1)
        logger.debug("ID mapping loaded from %s (%d entries)", path, len(self))


# ---------------------------------------------------------------------------
# FAISS Search Service
# ---------------------------------------------------------------------------


class FAISSSearchService:
    """
    Encapsulates the FAISS index and all search operations.

    Lifecycle:
        1. build_index(books)   — create index from book metadata.
        2. save()               — persist to disk.
        3. load()               — restore from disk.
        4. search(query, ...)   — retrieve nearest books.
        5. add_book(book)       — add a single book.
        6. remove_book(mongo_id)— remove (requires rebuild for FlatIP).
        7. rebuild(books)       — full rebuild.
    """

    def __init__(self):
        self._index: Optional[faiss.IndexIDMap] = None
        self._mapping = IDMapping()
        self._book_metadata: Dict[str, dict] = {}   # mongo_id -> metadata
        self._is_loaded = False

    # -- properties ---------------------------------------------------------

    @property
    def is_ready(self) -> bool:
        return self._index is not None and self._is_loaded

    @property
    def total_vectors(self) -> int:
        if self._index is None:
            return 0
        return self._index.ntotal

    # -- index building -----------------------------------------------------

    def build_index(self, books: List[dict]) -> dict:
        """
        Build a fresh FAISS index from a list of book metadata dicts.

        Each book dict must have at least '_id' (or 'id') plus the
        text fields used for embedding (title, author, ...).

        Returns a summary dict.
        """
        t0 = time.perf_counter()

        if not books:
            logger.warning("build_index called with an empty book list.")
            self._create_empty_index()
            return {"indexed": 0, "skipped": 0, "elapsed_ms": 0}

        self._mapping.clear()
        self._book_metadata.clear()

        # Prepare texts and IDs
        texts: List[str] = []
        faiss_ids: List[int] = []
        skipped = 0

        for book in books:
            mongo_id = str(book.get("_id") or book.get("id") or "")
            if not mongo_id:
                logger.warning("Skipping book with missing _id: %s", book.get("title", "?"))
                skipped += 1
                continue

            if self._mapping.has_mongo_id(mongo_id):
                logger.warning("Duplicate book _id=%s, skipping.", mongo_id)
                skipped += 1
                continue

            text = build_document_text(book)
            if not text.strip():
                logger.warning("Skipping book _id=%s: empty text.", mongo_id)
                skipped += 1
                continue

            fid = self._mapping.add(mongo_id)
            faiss_ids.append(fid)
            texts.append(text)
            self._book_metadata[mongo_id] = _sanitise_metadata(book)

        if not texts:
            self._create_empty_index()
            return {"indexed": 0, "skipped": skipped, "elapsed_ms": 0}

        # Generate embeddings (normalised for cosine similarity)
        embeddings = encode_texts(texts, normalize=True)

        # Build the flat inner-product index wrapped in IndexIDMap
        dim = embeddings.shape[1]
        flat_index = faiss.IndexFlatIP(dim)
        self._index = faiss.IndexIDMap(flat_index)

        ids_array = np.array(faiss_ids, dtype=np.int64)
        self._index.add_with_ids(embeddings, ids_array)

        self._is_loaded = True
        elapsed = (time.perf_counter() - t0) * 1000

        logger.info(
            "FAISS index built: %d vectors, %d skipped, %.1f ms",
            len(texts), skipped, elapsed,
        )

        return {
            "indexed": len(texts),
            "skipped": skipped,
            "elapsed_ms": round(elapsed, 2),
        }

    def _create_empty_index(self):
        flat_index = faiss.IndexFlatIP(config.EMBEDDING_DIM)
        self._index = faiss.IndexIDMap(flat_index)
        self._is_loaded = True

    # -- persistence --------------------------------------------------------

    def save(self, index_path: Optional[Path] = None, mapping_path: Optional[Path] = None):
        """Persist index and mapping to disk."""
        idx_p = index_path or config.INDEX_PATH
        map_p = mapping_path or config.MAPPING_PATH

        if self._index is None:
            raise RuntimeError("Cannot save: no index has been built.")

        idx_p.parent.mkdir(parents=True, exist_ok=True)

        # Write index to a temp file first, then rename for atomicity
        tmp_idx = idx_p.with_suffix(".tmp")
        faiss.write_index(self._index, str(tmp_idx))
        shutil.move(str(tmp_idx), str(idx_p))

        # Save mapping
        self._mapping.save(map_p)

        # Save metadata cache alongside
        meta_path = map_p.with_name("book_metadata_cache.json")
        tmp_meta = meta_path.with_suffix(".tmp")
        with open(tmp_meta, "w", encoding="utf-8") as fh:
            json.dump(self._book_metadata, fh, indent=2)
        shutil.move(str(tmp_meta), str(meta_path))

        logger.info(
            "FAISS index saved: %s (%d vectors), mapping: %s",
            idx_p, self.total_vectors, map_p,
        )

    def load(self, index_path: Optional[Path] = None, mapping_path: Optional[Path] = None) -> dict:
        """Load index and mapping from disk."""
        idx_p = index_path or config.INDEX_PATH
        map_p = mapping_path or config.MAPPING_PATH

        if not idx_p.exists():
            raise FileNotFoundError(f"FAISS index file not found: {idx_p}")
        if not map_p.exists():
            raise FileNotFoundError(f"ID mapping file not found: {map_p}")

        t0 = time.perf_counter()

        try:
            loaded_index = faiss.read_index(str(idx_p))
        except Exception as exc:
            raise RuntimeError(f"Failed to read FAISS index (possibly corrupted): {exc}")

        # Validate dimension
        if loaded_index.d != config.EMBEDDING_DIM:
            raise ValueError(
                f"Index dimension ({loaded_index.d}) does not match "
                f"configured EMBEDDING_DIM ({config.EMBEDDING_DIM})."
            )

        self._index = loaded_index
        self._mapping = IDMapping()
        self._mapping.load(map_p)

        # Load metadata cache if available
        meta_path = map_p.with_name("book_metadata_cache.json")
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as fh:
                self._book_metadata = json.load(fh)

        self._is_loaded = True
        elapsed = (time.perf_counter() - t0) * 1000

        logger.info(
            "FAISS index loaded: %d vectors, mapping: %d entries, %.1f ms",
            self.total_vectors, len(self._mapping), elapsed,
        )

        return {
            "vectors": self.total_vectors,
            "mappings": len(self._mapping),
            "elapsed_ms": round(elapsed, 2),
        }

    # -- search -------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = config.DEFAULT_TOP_K,
        filters: Optional[Dict[str, str]] = None,
    ) -> dict:
        """
        Semantic search: encode the query, search FAISS, apply metadata
        filters, and return ranked results.

        Parameters
        ----------
        query : str
            Natural-language query text.
        top_k : int
            Number of results to return after filtering.
        filters : dict, optional
            Metadata filters, e.g. {"category": "Programming", "author": "..."}.

        Returns
        -------
        dict with keys: query, results, total_candidates, filters_applied,
        search_time_ms.
        """
        if not self.is_ready:
            raise RuntimeError("FAISS index is not loaded. Build or load an index first.")

        if self.total_vectors == 0:
            return self._empty_response(query, filters)

        top_k = self._clamp_top_k(top_k)

        t0 = time.perf_counter()

        # 1. Encode query
        query_vec = encode_query(query, normalize=True)
        query_vec = validate_vector(query_vec, "query embedding")

        # 2. Search with candidate expansion to handle post-filtering
        has_filters = bool(filters)
        results = []

        if has_filters:
            results = self._search_with_filters(query_vec, top_k, filters)
        else:
            results = self._search_raw(query_vec, top_k)

        elapsed = (time.perf_counter() - t0) * 1000

        return {
            "query": query,
            "results": results,
            "total_candidates": self.total_vectors,
            "result_count": len(results),
            "filters_applied": filters or {},
            "search_time_ms": round(elapsed, 2),
            "distance_metric": "cosine_similarity",
        }

    def search_by_vector(
        self,
        query_vec: np.ndarray,
        top_k: int = config.DEFAULT_TOP_K,
        filters: Optional[Dict[str, str]] = None,
    ) -> dict:
        """
        Search using a pre-computed query vector (from the teammate's
        Embedding Generation Module).
        """
        if not self.is_ready:
            raise RuntimeError("FAISS index is not loaded.")

        if self.total_vectors == 0:
            return self._empty_response("<vector query>", filters)

        top_k = self._clamp_top_k(top_k)
        t0 = time.perf_counter()

        query_vec = validate_vector(query_vec, "query embedding")
        query_vec = _normalise(query_vec.copy())

        has_filters = bool(filters)
        if has_filters:
            results = self._search_with_filters(query_vec, top_k, filters)
        else:
            results = self._search_raw(query_vec, top_k)

        elapsed = (time.perf_counter() - t0) * 1000
        return {
            "query": "<vector>",
            "results": results,
            "total_candidates": self.total_vectors,
            "result_count": len(results),
            "filters_applied": filters or {},
            "search_time_ms": round(elapsed, 2),
            "distance_metric": "cosine_similarity",
        }

    # -- internal search helpers --------------------------------------------

    def _search_raw(self, query_vec: np.ndarray, top_k: int) -> List[dict]:
        """Unfiltered FAISS search."""
        k = min(top_k, self.total_vectors)
        scores, ids = self._index.search(query_vec, k)
        return self._build_results(scores[0], ids[0])

    def _search_with_filters(
        self, query_vec: np.ndarray, top_k: int, filters: Dict[str, str]
    ) -> List[dict]:
        """
        Progressively expand the FAISS retrieval window until enough
        results pass the metadata filters, or all vectors are exhausted.
        """
        request_k = min(
            top_k * config.CANDIDATE_EXPANSION_FACTOR,
            self.total_vectors,
        )

        for _ in range(config.MAX_EXPANSION_ROUNDS):
            scores, ids = self._index.search(query_vec, request_k)
            candidates = self._build_results(scores[0], ids[0])
            filtered = self._apply_filters(candidates, filters)

            if len(filtered) >= top_k or request_k >= self.total_vectors:
                return filtered[:top_k]

            # Expand the window
            request_k = min(request_k * 2, self.total_vectors)

        return filtered[:top_k]

    def _build_results(self, scores: np.ndarray, ids: np.ndarray) -> List[dict]:
        """Map FAISS IDs + scores to book result dicts."""
        results = []
        for rank, (score, fid) in enumerate(zip(scores, ids), start=1):
            fid_int = int(fid)
            if fid_int == -1:
                continue  # FAISS returns -1 for unfilled slots

            mongo_id = self._mapping.mongo_id(fid_int)
            if mongo_id is None:
                logger.warning("FAISS ID %d has no mapping, skipping.", fid_int)
                continue

            metadata = self._book_metadata.get(mongo_id, {})
            results.append({
                "book_id": mongo_id,
                "similarity_score": round(float(score), 6),
                "rank": rank,
                **metadata,
            })
        return results

    @staticmethod
    def _apply_filters(results: List[dict], filters: Dict[str, str]) -> List[dict]:
        """
        Apply metadata filters to search results.  Each filter value
        is matched case-insensitively as a substring of the
        corresponding metadata field.
        """
        filtered = []
        for result in results:
            match = True
            for key, value in filters.items():
                field_val = str(result.get(key, "")).lower()
                filter_val = str(value).lower()
                if filter_val not in field_val:
                    match = False
                    break
            if match:
                filtered.append(result)

        # Re-number ranks after filtering
        for i, r in enumerate(filtered, start=1):
            r["rank"] = i

        return filtered

    # -- index updates ------------------------------------------------------

    def add_book(self, book: dict) -> dict:
        """
        Add a single book to the existing index.

        For IndexFlatIP this is an O(1) append — no rebuild needed.
        """
        if not self.is_ready:
            raise RuntimeError("FAISS index is not loaded.")

        mongo_id = str(book.get("_id") or book.get("id") or "")
        if not mongo_id:
            raise ValueError("Book must have an '_id' field.")

        if self._mapping.has_mongo_id(mongo_id):
            logger.info("Book %s already indexed; updating instead.", mongo_id)
            return self.update_book(mongo_id, book)

        text = build_document_text(book)
        if not text.strip():
            raise ValueError(f"Book {mongo_id} produces empty text for embedding.")

        embedding = encode_texts([text], normalize=True)
        fid = self._mapping.add(mongo_id)
        ids_array = np.array([fid], dtype=np.int64)
        self._index.add_with_ids(embedding, ids_array)

        self._book_metadata[mongo_id] = _sanitise_metadata(book)

        logger.info("Book added to FAISS index: %s (fid=%d)", mongo_id, fid)
        return {"added": True, "book_id": mongo_id, "total_vectors": self.total_vectors}

    def update_book(self, mongo_id: str, new_book: dict) -> dict:
        """
        Update a book's embedding and metadata.

        For a flat index, updating requires a full rebuild because
        FAISS flat indexes do not support in-place vector replacement.
        Instead we do a lightweight approach: remove + re-add requires
        rebuild.  For the small dataset this is acceptable.
        """
        if not self.is_ready:
            raise RuntimeError("FAISS index is not loaded.")

        # Update metadata immediately
        self._book_metadata[mongo_id] = _sanitise_metadata(new_book)

        # Mark that a rebuild is recommended for vector accuracy
        logger.info(
            "Book %s metadata updated. A full rebuild is recommended "
            "to update the embedding vector.", mongo_id,
        )
        return {"updated": True, "book_id": mongo_id, "rebuild_recommended": True}

    def remove_book(self, mongo_id: str) -> dict:
        """
        Remove a book from the metadata and mapping.

        FAISS IndexFlatIP does not support removal.  The vector remains
        in the index but will be filtered out during search because
        the mapping no longer resolves.  A rebuild is recommended to
        reclaim space and avoid stale vectors.
        """
        if not self.is_ready:
            raise RuntimeError("FAISS index is not loaded.")

        fid = self._mapping.remove(mongo_id)
        self._book_metadata.pop(mongo_id, None)

        if fid is not None:
            logger.info("Book %s removed from mapping (fid=%d). Rebuild recommended.", mongo_id, fid)
        else:
            logger.warning("Book %s was not in the mapping.", mongo_id)

        return {"removed": fid is not None, "book_id": mongo_id, "rebuild_recommended": True}

    def rebuild(self, books: List[dict]) -> dict:
        """Full rebuild from a fresh list of books."""
        logger.info("Rebuilding FAISS index with %d books...", len(books))
        return self.build_index(books)

    # -- helpers ------------------------------------------------------------

    def _clamp_top_k(self, top_k: int) -> int:
        if top_k < 1:
            return 1
        if top_k > config.MAX_TOP_K:
            return config.MAX_TOP_K
        return top_k

    def _empty_response(self, query: str, filters: Optional[dict] = None) -> dict:
        return {
            "query": query,
            "results": [],
            "total_candidates": 0,
            "result_count": 0,
            "filters_applied": filters or {},
            "search_time_ms": 0.0,
            "distance_metric": "cosine_similarity",
        }

    def get_status(self) -> dict:
        return {
            "is_ready": self.is_ready,
            "total_vectors": self.total_vectors,
            "embedding_dim": config.EMBEDDING_DIM,
            "distance_metric": config.DISTANCE_METRIC,
            "model_name": config.SBERT_MODEL_NAME,
            "index_path": str(config.INDEX_PATH),
            "mapping_entries": len(self._mapping),
        }


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _sanitise_metadata(book: dict) -> dict:
    """Extract only the fields we want to cache with search results."""
    return {
        "title": book.get("title", ""),
        "author": book.get("author", ""),
        "category": book.get("category", ""),
        "keywords": book.get("keywords", ""),
        "description": book.get("description", ""),
        "shelf": book.get("shelf", ""),
        "rack": book.get("rack", ""),
        "location": book.get("location", ""),
    }
