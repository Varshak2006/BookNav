"""
FAISS Vector Search Module — Vector Validator & Normalization.

Provides validation routines for query vectors, batch vectors, and
mathematically correct L2 normalization for cosine similarity search.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Union
import faiss
import numpy as np


class VectorValidationError(ValueError):
    """Raised when a vector violates numeric, finite, or dimensional constraints."""
    pass


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
    expected_model: str,
    expected_dim: int,
    expected_metric: str,
    expected_index_type: str = "FLAT",
) -> Dict[str, Any]:
    """
    Strictly validates FAISS index, ID mapping, and metadata files against
    compatibility, integrity, and generation-consistency requirements.
    """
    idx_p = Path(index_path)
    map_p = Path(mapping_path)
    meta_p = Path(metadata_path)

    if not idx_p.exists():
        return {
            "valid": False,
            "status_code": "INDEX_MISSING",
            "errors": [f"Index file does not exist: {idx_p}"]
        }

    if not map_p.exists():
        return {
            "valid": False,
            "status_code": "MAPPING_MISSING",
            "errors": [f"Mapping file does not exist: {map_p}"]
        }

    if not meta_p.exists():
        return {
            "valid": False,
            "status_code": "METADATA_MISSING",
            "errors": [f"Metadata file does not exist: {meta_p}"]
        }

    try:
        index = faiss.read_index(str(idx_p))
    except Exception as exc:
        return {
            "valid": False,
            "status_code": "CORRUPTED_INDEX",
            "errors": [f"Corrupted or unreadable FAISS index file: {exc}"]
        }

    try:
        with open(map_p, "r", encoding="utf-8") as f:
            mapping_data = json.load(f)
    except Exception as exc:
        return {
            "valid": False,
            "status_code": "CORRUPTED_MAPPING",
            "errors": [f"Corrupted or unreadable ID mapping JSON file: {exc}"]
        }

    try:
        with open(meta_p, "r", encoding="utf-8") as f:
            meta_data = json.load(f)
    except Exception as exc:
        return {
            "valid": False,
            "status_code": "CORRUPTED_METADATA",
            "errors": [f"Corrupted or unreadable index metadata JSON file: {exc}"]
        }

    # Extract dimensions and counts
    index_dim = index.d
    index_ntotal = index.ntotal
    mappings = mapping_data.get("mappings", [])
    map_count = len(mappings)
    meta_count = meta_data.get("vector_count")
    meta_dim = meta_data.get("embedding_dim")
    meta_metric = meta_data.get("distance_metric")
    meta_model = meta_data.get("model_name")
    meta_gen = meta_data.get("generation_id")
    map_gen = mapping_data.get("generation_id")

    errors = []

    # Dimension validation
    if index_dim != expected_dim:
        return {
            "valid": False,
            "status_code": "DIMENSION_MISMATCH",
            "errors": [f"Index dimension mismatch: got {index_dim}, expected {expected_dim}"]
        }
    if meta_dim is not None and meta_dim != expected_dim:
        return {
            "valid": False,
            "status_code": "DIMENSION_MISMATCH",
            "errors": [f"Metadata dimension mismatch: got {meta_dim}, expected {expected_dim}"]
        }

    # Metric validation
    if meta_metric is not None and meta_metric.upper() != expected_metric.upper():
        return {
            "valid": False,
            "status_code": "METRIC_MISMATCH",
            "errors": [f"Metric mismatch: metadata records '{meta_metric}', expected '{expected_metric}'"]
        }

    # Model validation
    if meta_model is not None and meta_model != expected_model:
        return {
            "valid": False,
            "status_code": "MODEL_MISMATCH",
            "errors": [f"Embedding model mismatch: metadata records '{meta_model}', expected '{expected_model}'"]
        }

    # Generation ID validation
    if not meta_gen or not map_gen or meta_gen != map_gen:
        return {
            "valid": False,
            "status_code": "GENERATION_MISMATCH",
            "errors": [f"Generation ID mismatch: metadata has '{meta_gen}', mapping has '{map_gen}'"]
        }

    # Vector count validation
    if index_ntotal != map_count:
        return {
            "valid": False,
            "status_code": "COUNT_MISMATCH",
            "errors": [f"Count mismatch: index has {index_ntotal} vectors, mapping has {map_count} entries"]
        }
    if meta_count is not None and meta_count != index_ntotal:
        return {
            "valid": False,
            "status_code": "COUNT_MISMATCH",
            "errors": [f"Count mismatch: index has {index_ntotal} vectors, metadata records {meta_count}"]
        }

    # Vector ID uniqueness and alignment
    map_faiss_ids = [m.get("faiss_id") for m in mappings if "faiss_id" in m]
    if len(map_faiss_ids) != len(set(map_faiss_ids)):
        return {
            "valid": False,
            "status_code": "DUPLICATE_MAPPING_IDS",
            "errors": ["Duplicate FAISS IDs found in mapping table"]
        }

    if hasattr(index, "id_map"):
        index_ids = faiss.vector_to_array(index.id_map).tolist()
        if set(index_ids) != set(map_faiss_ids):
            return {
                "valid": False,
                "status_code": "ID_MISMATCH",
                "errors": ["Exact ID mismatch between FAISS index and mapping table"]
            }

    return {
        "valid": True,
        "status_code": "READY",
        "errors": [],
        "details": {
            "vector_count": index_ntotal,
            "mapping_count": map_count,
            "dimension": index_dim,
            "metric": expected_metric,
            "model_name": expected_model,
            "generation_id": meta_gen,
        }
    }
