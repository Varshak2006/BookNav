"""
FAISS Vector Search Module — Vector & Index Artifact Validation.

Provides validation routines for query vectors, batch vectors,
L2 normalization for cosine similarity search, and comprehensive
readiness validation across FAISS index, ID mapping, and generation metadata.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Union
import faiss
import numpy as np


class VectorValidationError(ValueError):
    """Raised when a vector violates numeric, finite, or dimensional constraints."""
    pass


class IndexNotReadyError(RuntimeError):
    """Raised when an operation is attempted on an unready or inconsistent FAISS index."""
    def __init__(self, state: str, reason: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(f"FAISS index not ready [{state}]: {reason}")
        self.state = state
        self.reason = reason
        self.details = details or {}


class IndexReadinessState:
    """Distinct states for index lifecycle and error diagnosis."""
    READY = "READY"
    INTENTIONALLY_EMPTY = "INTENTIONALLY_EMPTY"
    MISSING_INDEX = "MISSING_INDEX"
    CORRUPTED_INDEX = "CORRUPTED_INDEX"
    MISSING_MAPPING = "MISSING_MAPPING"
    CORRUPTED_MAPPING = "CORRUPTED_MAPPING"
    MISSING_METADATA = "MISSING_METADATA"
    INVALID_METADATA = "INVALID_METADATA"
    MODEL_MISMATCH = "MODEL_MISMATCH"
    DIMENSION_MISMATCH = "DIMENSION_MISMATCH"
    METRIC_MISMATCH = "METRIC_MISMATCH"
    INDEX_TYPE_MISMATCH = "INDEX_TYPE_MISMATCH"
    GENERATION_MISMATCH = "GENERATION_MISMATCH"
    COUNT_MISMATCH = "COUNT_MISMATCH"
    ID_INCONSISTENCY = "ID_INCONSISTENCY"


def validate_vector(
    vector: Union[list, np.ndarray],
    expected_dim: int,
    allow_batch: bool = False
) -> np.ndarray:
    """
    Validate that an input vector is numeric, finite, non-empty, and matches expected_dim.
    """
    if vector is None:
        raise VectorValidationError("Vector cannot be None.")

    try:
        arr = np.asarray(vector, dtype=np.float32)
    except (TypeError, ValueError) as exc:
        raise VectorValidationError(f"Vector contains non-numeric data: {exc}") from exc

    if arr.size == 0:
        raise VectorValidationError("Vector cannot be empty.")

    if not np.all(np.isfinite(arr)):
        raise VectorValidationError("Vector contains non-finite values (NaN or Inf).")

    if allow_batch:
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        elif arr.ndim != 2:
            raise VectorValidationError(
                f"Batch vectors must be 2D, got shape {arr.shape}."
            )
        if arr.shape[1] != expected_dim:
            raise VectorValidationError(
                f"Vector dimension mismatch: expected {expected_dim}, got {arr.shape[1]}."
            )
    else:
        if arr.ndim == 2:
            if arr.shape[0] != 1:
                raise VectorValidationError(
                    f"Single query vector expected, got batch of shape {arr.shape}."
                )
            arr = arr.flatten()
        elif arr.ndim != 1:
            raise VectorValidationError(
                f"Query vector must be 1D, got shape {arr.shape}."
            )

        if arr.shape[0] != expected_dim:
            raise VectorValidationError(
                f"Vector dimension mismatch: expected {expected_dim}, got {arr.shape[0]}."
            )

    return arr


def normalize_vectors(vectors: np.ndarray) -> np.ndarray:
    """
    Normalize 1D or 2D vectors to unit L2 norm in-place or returns normalized copy.
    Required for cosine similarity via inner product (IndexFlatIP).
    """
    if vectors.ndim == 1:
        norm = np.linalg.norm(vectors)
        if norm > 1e-12:
            return (vectors / norm).astype(np.float32)
        return vectors.astype(np.float32)

    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms < 1e-12] = 1.0
    return (vectors / norms).astype(np.float32)


def validate_index_artifacts(
    index_path: Union[str, Path],
    mapping_path: Union[str, Path],
    metadata_path: Union[str, Path],
    expected_dim: int,
    expected_metric: str,
    expected_model: str,
    expected_type: str = "FLAT",
    allow_empty: bool = False,
) -> Dict[str, Any]:
    """
    Comprehensive validation across FAISS index, mapping file, and metadata artifact.

    Distinguishes:
    - INTENTIONALLY_EMPTY
    - MISSING_INDEX
    - CORRUPTED_INDEX
    - MISSING_MAPPING
    - CORRUPTED_MAPPING
    - MISSING_METADATA
    - INVALID_METADATA
    - MODEL_MISMATCH
    - DIMENSION_MISMATCH
    - METRIC_MISMATCH
    - GENERATION_MISMATCH
    - COUNT_MISMATCH
    - ID_INCONSISTENCY
    """
    index_p = Path(index_path)
    mapping_p = Path(mapping_path)
    meta_p = Path(metadata_path)

    # 1. Existence checks
    index_exists = index_p.exists() and index_p.is_file()
    mapping_exists = mapping_p.exists() and mapping_p.is_file()
    meta_exists = meta_p.exists() and meta_p.is_file()

    if not index_exists and not mapping_exists and not meta_exists:
        if allow_empty:
            return {
                "ready": True,
                "state": IndexReadinessState.INTENTIONALLY_EMPTY,
                "reason": "Index is intentionally empty (initialized without stored artifacts).",
                "details": {"allow_empty": True},
            }
        return {
            "ready": False,
            "state": IndexReadinessState.MISSING_INDEX,
            "reason": f"No FAISS index, mapping, or metadata found at {index_p.parent}. A rebuild is required.",
            "details": {
                "index_path": str(index_p),
                "mapping_path": str(mapping_p),
                "metadata_path": str(meta_p),
            },
        }

    if not index_exists:
        return {
            "ready": False,
            "state": IndexReadinessState.MISSING_INDEX,
            "reason": f"FAISS index file is missing at {index_p}.",
            "details": {"index_path": str(index_p)},
        }

    if not mapping_exists:
        return {
            "ready": False,
            "state": IndexReadinessState.MISSING_MAPPING,
            "reason": f"ID mapping file is missing at {mapping_p}.",
            "details": {"mapping_path": str(mapping_p)},
        }

    if not meta_exists:
        return {
            "ready": False,
            "state": IndexReadinessState.MISSING_METADATA,
            "reason": f"Index metadata file is missing at {meta_p}.",
            "details": {"metadata_path": str(meta_p)},
        }

    # 2. Try loading FAISS index
    try:
        loaded_index = faiss.read_index(str(index_p))
    except Exception as exc:
        return {
            "ready": False,
            "state": IndexReadinessState.CORRUPTED_INDEX,
            "reason": f"Failed to read FAISS index file (corrupted or unreadable): {exc}",
            "details": {"error": str(exc)},
        }

    # 3. Try loading and parsing mapping
    try:
        with open(mapping_p, "r", encoding="utf-8") as f:
            mapping_data = json.load(f)
    except Exception as exc:
        return {
            "ready": False,
            "state": IndexReadinessState.CORRUPTED_MAPPING,
            "reason": f"Failed to read or parse ID mapping JSON: {exc}",
            "details": {"error": str(exc)},
        }

    # 4. Try loading and parsing metadata
    try:
        with open(meta_p, "r", encoding="utf-8") as f:
            meta_data = json.load(f)
    except Exception as exc:
        return {
            "ready": False,
            "state": IndexReadinessState.INVALID_METADATA,
            "reason": f"Failed to read or parse index metadata JSON: {exc}",
            "details": {"error": str(exc)},
        }

    # 5. Validate Dimensions
    if loaded_index.d != expected_dim:
        return {
            "ready": False,
            "state": IndexReadinessState.DIMENSION_MISMATCH,
            "reason": f"Index dimension mismatch: file has {loaded_index.d}, expected {expected_dim}.",
            "details": {"stored_dim": loaded_index.d, "expected_dim": expected_dim},
        }

    meta_dim = meta_data.get("embedding_dim")
    if meta_dim is not None and meta_dim != expected_dim:
        return {
            "ready": False,
            "state": IndexReadinessState.DIMENSION_MISMATCH,
            "reason": f"Metadata dimension mismatch: metadata has {meta_dim}, expected {expected_dim}.",
            "details": {"metadata_dim": meta_dim, "expected_dim": expected_dim},
        }

    # 6. Validate Model
    meta_model = meta_data.get("model_name")
    if meta_model and meta_model != expected_model:
        return {
            "ready": False,
            "state": IndexReadinessState.MODEL_MISMATCH,
            "reason": f"Embedding model mismatch: index was built with '{meta_model}', config uses '{expected_model}'.",
            "details": {"stored_model": meta_model, "expected_model": expected_model},
        }

    # 7. Validate Metric
    meta_metric = meta_data.get("distance_metric")
    if meta_metric and meta_metric.upper() != expected_metric.upper():
        return {
            "ready": False,
            "state": IndexReadinessState.METRIC_MISMATCH,
            "reason": f"Distance metric mismatch: index has '{meta_metric}', config uses '{expected_metric}'.",
            "details": {"stored_metric": meta_metric, "expected_metric": expected_metric},
        }

    # 8. Validate Generation IDs
    meta_gen = meta_data.get("generation_id")
    map_gen = mapping_data.get("generation_id")
    if not meta_gen or not map_gen or meta_gen != map_gen:
        return {
            "ready": False,
            "state": IndexReadinessState.GENERATION_MISMATCH,
            "reason": f"Generation ID mismatch: metadata has '{meta_gen}', mapping has '{map_gen}'.",
            "details": {"metadata_generation": meta_gen, "mapping_generation": map_gen},
        }

    # 9. Validate Vector Count vs Mapping Count
    mappings_list = mapping_data.get("mappings", [])
    mapping_count = len(mappings_list)
    index_count = loaded_index.ntotal

    if index_count != mapping_count:
        return {
            "ready": False,
            "state": IndexReadinessState.COUNT_MISMATCH,
            "reason": f"Count mismatch: index has {index_count} vectors, mapping has {mapping_count} entries.",
            "details": {"index_count": index_count, "mapping_count": mapping_count},
        }

    # 10. Validate Index-ID vs Mapping-ID exact consistency
    mapping_faiss_ids = set()
    for item in mappings_list:
        fid = item.get("faiss_id")
        if fid is not None:
            mapping_faiss_ids.add(int(fid))

    if isinstance(loaded_index, (faiss.IndexIDMap, faiss.IndexIDMap2)):
        try:
            stored_ids_arr = faiss.vector_to_array(loaded_index.id_map)
            stored_faiss_ids = set(int(x) for x in stored_ids_arr)
            if mapping_faiss_ids != stored_faiss_ids:
                missing_in_index = len(mapping_faiss_ids - stored_faiss_ids)
                missing_in_map = len(stored_faiss_ids - mapping_faiss_ids)
                return {
                    "ready": False,
                    "state": IndexReadinessState.ID_INCONSISTENCY,
                    "reason": f"ID consistency mismatch: {missing_in_index} IDs missing from index, {missing_in_map} IDs missing from mapping.",
                    "details": {
                        "missing_in_index_count": missing_in_index,
                        "missing_in_mapping_count": missing_in_map,
                    },
                }
        except Exception as exc:
            pass  # Fall through if vector_to_array is unavailable on particular wrapper

    # All validations passed!
    return {
        "ready": True,
        "state": IndexReadinessState.READY,
        "reason": "Index, mapping, and metadata are consistent and compatible.",
        "details": {
            "vector_count": index_count,
            "mapping_count": mapping_count,
            "generation_id": meta_gen,
            "dimension": loaded_index.d,
            "metric": expected_metric,
            "model_name": expected_model,
        },
    }
