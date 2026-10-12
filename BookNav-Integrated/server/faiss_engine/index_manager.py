"""
FAISS Vector Search Module — Index Construction, Persistence & Search Manager.

Supports exact (FlatIP/FlatL2) and approximate (IVFFlat/HNSWFlat) indices.
Handles safe atomic persistence, index loading, dimensionality validation,
and vector retrieval.
"""

import os
from pathlib import Path
from typing import Optional, Tuple
import faiss
import numpy as np

from .config import (
    DISTANCE_METRIC,
    EMBEDDING_DIM,
    HNSW_EF_CONSTRUCTION,
    HNSW_EF_SEARCH,
    HNSW_M,
    INDEX_PATH,
    INDEX_TYPE,
    IVF_NLIST,
    IVF_NPROBE,
)
from .validator import VectorValidationError, validate_vector


class IndexManager:
    """
    Encapsulates FAISS index lifecycle: creation, training (if ANN),
    incremental addition, searching, and atomic file persistence.
    """

    def __init__(
        self,
        dimension: int = EMBEDDING_DIM,
        metric: str = DISTANCE_METRIC,
        index_type: str = INDEX_TYPE,
        index_path: Path = INDEX_PATH,
    ):
        self.dimension = dimension
        self.metric = metric.upper()
        self.index_type = index_type.upper()
        self.index_path = Path(index_path)
        self.index: Optional[faiss.Index] = None

    @property
    def is_initialized(self) -> bool:
        return self.index is not None

    @property
    def count(self) -> int:
        return self.index.ntotal if self.index is not None else 0

    def _resolve_metric(self) -> int:
        if self.metric == "IP":
            return faiss.METRIC_INNER_PRODUCT
        elif self.metric == "L2":
            return faiss.METRIC_L2
        else:
            raise ValueError(f"Unsupported metric: '{self.metric}'. Use 'IP' or 'L2'.")

    def build_empty_index(
        self,
        index_type: Optional[str] = None,
        use_id_map: bool = True
    ) -> faiss.Index:
        """
        Construct a fresh, empty FAISS index according to configured type and metric.
        """
        itype = (index_type or self.index_type).upper()
        metric_faiss = self._resolve_metric()

        if itype == "FLAT":
            base_index = (
                faiss.IndexFlatIP(self.dimension)
                if self.metric == "IP"
                else faiss.IndexFlatL2(self.dimension)
            )
        elif itype == "HNSW":
            base_index = faiss.IndexHNSWFlat(self.dimension, HNSW_M, metric_faiss)
            base_index.hnsw.efConstruction = HNSW_EF_CONSTRUCTION
            base_index.hnsw.efSearch = HNSW_EF_SEARCH
        elif itype == "IVF":
            quantizer = (
                faiss.IndexFlatIP(self.dimension)
                if self.metric == "IP"
                else faiss.IndexFlatL2(self.dimension)
            )
            base_index = faiss.IndexIVFFlat(
                quantizer, self.dimension, IVF_NLIST, metric_faiss
            )
            base_index.nprobe = IVF_NPROBE
        else:
            raise ValueError(f"Unsupported index type: '{itype}'. Choose FLAT, HNSW, or IVF.")

        if use_id_map:
            # Wrap with IndexIDMap2 to support explicit 64-bit vector IDs and removals
            self.index = faiss.IndexIDMap2(base_index)
        else:
            self.index = base_index

        return self.index

    def add_vectors(self, vectors: np.ndarray, ids: Optional[np.ndarray] = None):
        """
        Add vectors to index. If index uses IndexIDMap, explicit IDs are required.
        """
        if self.index is None:
            self.build_empty_index()

        vectors = validate_vector(vectors, self.dimension, allow_batch=True)

        # If index requires training (e.g. IVF) and is not yet trained
        if not self.index.is_trained:
            if len(vectors) < IVF_NLIST:
                raise ValueError(
                    f"IVF index requires at least {IVF_NLIST} vectors to train; got {len(vectors)}."
                )
            self.index.train(vectors)

        if isinstance(self.index, (faiss.IndexIDMap, faiss.IndexIDMap2)):
            if ids is None:
                start_id = self.index.ntotal
                ids = np.arange(start_id, start_id + len(vectors), dtype=np.int64)
            else:
                ids = np.asarray(ids, dtype=np.int64)
                if len(ids) != len(vectors):
                    raise ValueError("Length of IDs must match number of vectors.")
            self.index.add_with_ids(vectors, ids)
        else:
            self.index.add(vectors)

    def remove_ids(self, ids: np.ndarray) -> int:
        """
        Remove vectors by ID. Only supported by IndexIDMap2 or Flat with IDMap.
        """
        if self.index is None:
            return 0
        id_arr = np.asarray(ids, dtype=np.int64)
        if hasattr(self.index, "remove_ids"):
            return self.index.remove_ids(id_arr)
        return 0

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Search for nearest neighbors of a single query vector.

        Parameters:
            query_vector: 1D or (1, D) float32 numpy array.
            top_k: Number of neighbors to retrieve.

        Returns:
            Tuple of (scores, indices) arrays of shape (1, k).
        """
        if self.index is None or self.index.ntotal == 0:
            return np.empty((1, 0), dtype=np.float32), np.empty((1, 0), dtype=np.int64)

        q = validate_vector(query_vector, self.dimension, allow_batch=False).reshape(1, -1)
        k = max(1, min(int(top_k), self.index.ntotal))

        # Perform FAISS search
        scores, indices = self.index.search(q, k)
        return scores, indices

    def save(self, path: Optional[Path] = None):
        """
        Persist FAISS index atomically to disk using a temporary file.
        """
        if self.index is None:
            raise RuntimeError("Cannot save an uninitialized FAISS index.")

        target_path = Path(path or self.index_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = target_path.with_suffix(".tmp")

        faiss.write_index(self.index, str(temp_path))

        if target_path.exists():
            os.replace(temp_path, target_path)
        else:
            temp_path.rename(target_path)

    def load(self, path: Optional[Path] = None) -> bool:
        """
        Load index from disk. Validates dimensionality and integrity.
        Returns True if loaded, False if file does not exist.
        """
        target_path = Path(path or self.index_path)
        if not target_path.exists():
            return False

        try:
            loaded_index = faiss.read_index(str(target_path))
            if loaded_index.d != self.dimension:
                raise VectorValidationError(
                    f"Index dimension mismatch: file has {loaded_index.d}, expected {self.dimension}."
                )
            self.index = loaded_index
            return True
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load FAISS index from {target_path}: {exc}"
            ) from exc
