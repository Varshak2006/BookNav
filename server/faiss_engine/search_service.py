"""
FAISS Vector Search Module — End-to-End Search Service.

Coordinates query vector validation, FAISS nearest-neighbor retrieval,
candidate expansion, metadata filtering, similarity score formatting,
optional relevance thresholding, and final ranked results formatting.
"""

from typing import Any, Callable, Dict, List, Optional, Union
import numpy as np

from .config import (
    CANDIDATE_EXPANSION_FACTOR,
    DEFAULT_TOP_K,
    DISTANCE_METRIC,
    EMBEDDING_DIM,
    MAX_TOP_K,
)
from .embedding_adapter import EmbeddingAdapter
from .id_mapping import IdMappingManager
from .index_manager import IndexManager
from .validator import IndexNotReadyError, normalize_vectors, validate_vector


class SearchService:
    """
    Search service integrating IndexManager, IdMappingManager, and EmbeddingAdapter.
    """

    def __init__(
        self,
        index_manager: IndexManager,
        id_mapping: IdMappingManager,
        embedding_adapter: Optional[EmbeddingAdapter] = None,
        readiness_checker: Optional[Callable[[], Dict[str, Any]]] = None,
    ):
        self.index_manager = index_manager
        self.id_mapping = id_mapping
        self.embedding_adapter = embedding_adapter or EmbeddingAdapter(
            expected_dim=index_manager.dimension
        )
        self.readiness_checker = readiness_checker

    # Filter fields supported by BookNav schema
    SUPPORTED_FILTERS = frozenset({
        "author", "category", "shelf", "rack", "location", "keywords", "title",
    })

    def _matches_filters(self, metadata: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """
        Evaluate if a book's metadata satisfies requested library filters.
        Supported filter fields: author, category, shelf, rack, location, keywords, title.
        """
        if not filters:
            return True

        for filter_key, filter_val in filters.items():
            if filter_val is None or str(filter_val).strip() == "":
                continue

            target_str = str(filter_val).strip().lower()
            field_val = str(metadata.get(filter_key, "")).strip().lower()

            # Case-insensitive substring match for all supported fields
            if target_str not in field_val:
                return False

        return True

    @staticmethod
    def validate_filters(filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate filter keys against supported fields.
        Raises ValueError for unsupported filter fields.
        Returns cleaned filters (empty values removed).
        """
        if not filters:
            return {}

        cleaned = {}
        for key, val in filters.items():
            if key not in SearchService.SUPPORTED_FILTERS:
                raise ValueError(
                    f"Unsupported filter field: '{key}'. "
                    f"Supported fields: {sorted(SearchService.SUPPORTED_FILTERS)}"
                )
            if val is not None and str(val).strip() != "":
                cleaned[key] = val
        return cleaned

    def search(
        self,
        query: Union[str, list, np.ndarray],
        top_k: int = DEFAULT_TOP_K,
        filters: Optional[Dict[str, Any]] = None,
        candidate_expansion: Optional[int] = None,
        min_score: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Execute vector similarity search with metadata filtering and optional relevance score threshold.

        Parameters:
            query: User text string OR pre-computed 1D float32 vector.
            top_k: Number of desired ranked results (1 to MAX_TOP_K).
            filters: Dictionary of metadata filters (e.g., {"category": "Poetry"}).
            candidate_expansion: Multiplier for candidate pool when filtering is active.
            min_score: Optional minimum relevance score threshold. Default None (disabled).

        Returns:
            Dict containing:
                - query: Original query text or representation
                - total_indexed: Total vectors in index
                - metric: Similarity metric name
                - results: List of ranked result objects with book details and scores
        """
        if self.readiness_checker:
            readiness = self.readiness_checker()
            if not readiness.get("ready"):
                raise IndexNotReadyError(
                    state=readiness.get("state", "UNKNOWN"),
                    reason=readiness.get("reason", "FAISS index is not ready for search."),
                    details=readiness.get("details"),
                )

        top_k = max(1, min(int(top_k), MAX_TOP_K))
        filters = self.validate_filters(filters or {})
        expansion_factor = candidate_expansion or CANDIDATE_EXPANSION_FACTOR

        if not self.index_manager.is_initialized or self.index_manager.count == 0:
            return {
                "total_indexed": 0,
                "metric": self.index_manager.metric,
                "results_count": 0,
                "results": [],
                "message": "Index is empty or not initialized."
            }

        # 1. Obtain and validate query vector
        if isinstance(query, str):
            query_text = query.strip()
            if not query_text:
                raise ValueError("Query string cannot be empty.")
            should_normalize = (self.index_manager.metric == "IP")
            query_vector = self.embedding_adapter.encode_query(query_text, normalize=should_normalize)
        else:
            query_text = "<vector_input>"
            query_vector = validate_vector(query, self.index_manager.dimension, allow_batch=False)
            if self.index_manager.metric == "IP":
                query_vector = normalize_vectors(query_vector)

        # 2. Determine initial candidate pool size
        total_vectors = self.index_manager.count
        if filters:
            search_k = min(total_vectors, max(top_k * expansion_factor, 100))
        else:
            search_k = min(total_vectors, top_k)

        # 3. Search FAISS index
        scores, indices = self.index_manager.search(query_vector, top_k=search_k)
        flat_scores = scores[0]
        flat_indices = indices[0]

        # Helper to collect matching candidates
        def collect_candidates(f_scores, f_indices):
            matched = []
            for raw_score, faiss_id in zip(f_scores, f_indices):
                fid = int(faiss_id)
                if fid < 0:
                    continue
                mongo_id = self.id_mapping.get_book_id(fid)
                if mongo_id is None:
                    continue
                metadata = self.id_mapping.get_metadata(fid) or {}
                if not self._matches_filters(metadata, filters):
                    continue

                score_val = float(raw_score)
                # If a calibrated threshold is provided, filter out items failing the threshold
                if min_score is not None:
                    if self.index_manager.metric == "IP" and score_val < min_score:
                        continue
                    elif self.index_manager.metric == "L2" and score_val > min_score:
                        continue

                matched.append({
                    "book_id": mongo_id,
                    "title": metadata.get("title", "Untitled"),
                    "author": metadata.get("author", "Unknown"),
                    "category": metadata.get("category", ""),
                    "description": metadata.get("description", ""),
                    "shelf": metadata.get("shelf", ""),
                    "rack": metadata.get("rack", ""),
                    "location": metadata.get("location", ""),
                    "keywords": metadata.get("keywords", ""),
                    "raw_score": score_val,
                })
                if len(matched) >= top_k:
                    break
            return matched

        candidates = collect_candidates(flat_scores, flat_indices)

        # 4. Adaptive expansion: if filters are active and matches < top_k and search_k < total_vectors
        if filters and len(candidates) < top_k and search_k < total_vectors:
            search_k = total_vectors
            scores, indices = self.index_manager.search(query_vector, top_k=search_k)
            candidates = collect_candidates(scores[0], indices[0])

        # 5. Format similarity scores and assign final rank
        metric_name = (
            "cosine_similarity"
            if self.index_manager.metric == "IP"
            else "squared_l2_distance"
        )

        results = []
        for rank_idx, item in enumerate(candidates, start=1):
            item_out = dict(item)
            raw = item_out.pop("raw_score")
            item_out["rank"] = rank_idx
            item_out["score"] = round(raw, 4)
            item_out["metric"] = metric_name
            results.append(item_out)

        return {
            "query": query_text,
            "total_indexed": total_vectors,
            "candidates_examined": int(search_k),
            "filters_applied": filters,
            "metric": metric_name,
            "threshold_applied": min_score,
            "results_count": len(results),
            "results": results
        }
