"""
FAISS Vector Search Module — Index Metadata & Generation Tracking.

Stores and validates metadata about the FAISS index to ensure:
1. Index and mapping files belong to the same generation (consistency).
2. The embedding model configuration is compatible with the stored index.
3. Corrupted or partially written artifacts are detected before activation.

Recovery Procedure:
    If index_metadata.json is missing or has a mismatched generation_id:
    1. Do NOT activate the index/mapping pair.
    2. Check for .prev backup files in faiss_data/.
    3. If valid .prev files exist, restore them.
    4. If no valid backups exist, trigger a full rebuild.
"""

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional


class IndexMetadata:
    """
    Tracks index generation, model configuration, and artifact consistency.
    """

    def __init__(self, metadata_path: Path):
        self.metadata_path = Path(metadata_path)
        self._data: Dict[str, Any] = {}

    @property
    def generation_id(self) -> Optional[str]:
        return self._data.get("generation_id")

    @property
    def model_name(self) -> Optional[str]:
        return self._data.get("model_name")

    @property
    def embedding_dim(self) -> Optional[int]:
        return self._data.get("embedding_dim")

    @property
    def distance_metric(self) -> Optional[str]:
        return self._data.get("distance_metric")

    @property
    def index_type(self) -> Optional[str]:
        return self._data.get("index_type")

    @property
    def vector_count(self) -> Optional[int]:
        return self._data.get("vector_count")

    @property
    def data(self) -> Dict[str, Any]:
        return dict(self._data)

    @staticmethod
    def create_generation_id() -> str:
        """Generate a unique generation identifier."""
        return f"{int(time.time())}_{uuid.uuid4().hex[:8]}"

    def set(
        self,
        generation_id: str,
        model_name: str,
        embedding_dim: int,
        distance_metric: str,
        index_type: str,
        vector_count: int,
        **extra: Any,
    ):
        """Set metadata for a new index generation."""
        self._data = {
            "version": 1,
            "generation_id": generation_id,
            "model_name": model_name,
            "embedding_dim": embedding_dim,
            "distance_metric": distance_metric,
            "index_type": index_type,
            "vector_count": vector_count,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            **extra,
        }

    def save(self):
        """Persist metadata atomically."""
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.metadata_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)
        if os.path.exists(self.metadata_path):
            os.replace(temp_path, self.metadata_path)
        else:
            temp_path.rename(self.metadata_path)

    def load(self) -> bool:
        """Load metadata from disk. Returns False if file doesn't exist."""
        if not self.metadata_path.exists():
            return False
        try:
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
            return True
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load index metadata from {self.metadata_path}: {exc}"
            ) from exc

    def validate_compatibility(
        self,
        model_name: str,
        embedding_dim: int,
        distance_metric: str,
    ) -> Dict[str, Any]:
        """
        Check if current metadata is compatible with expected configuration.

        Returns:
            Dict with 'compatible' (bool), 'issues' (list of strings).
        """
        issues = []

        if not self._data:
            return {"compatible": False, "issues": ["No metadata loaded."]}

        stored_dim = self._data.get("embedding_dim")
        if stored_dim is not None and stored_dim != embedding_dim:
            issues.append(
                f"Embedding dimension mismatch: index has {stored_dim}, "
                f"expected {embedding_dim}."
            )

        stored_metric = self._data.get("distance_metric")
        if stored_metric is not None and stored_metric.upper() != distance_metric.upper():
            issues.append(
                f"Distance metric mismatch: index has '{stored_metric}', "
                f"expected '{distance_metric}'."
            )

        stored_model = self._data.get("model_name")
        if stored_model is not None and stored_model != model_name:
            issues.append(
                f"Model mismatch: index was built with '{stored_model}', "
                f"current config uses '{model_name}'. A rebuild is required."
            )

        return {
            "compatible": len(issues) == 0,
            "issues": issues,
        }

    def validate_generation(self, mapping_generation_id: Optional[str]) -> Dict[str, Any]:
        """
        Check if the mapping's generation_id matches the index metadata.

        Returns:
            Dict with 'consistent' (bool), 'issues' (list of strings).
        """
        issues = []
        meta_gen = self._data.get("generation_id")

        if meta_gen is None:
            issues.append("Index metadata has no generation_id.")
        elif mapping_generation_id is None:
            issues.append("Mapping has no generation_id.")
        elif meta_gen != mapping_generation_id:
            issues.append(
                f"Generation mismatch: index metadata has '{meta_gen}', "
                f"mapping has '{mapping_generation_id}'. "
                "Index and mapping may not correspond to the same build."
            )

        return {
            "consistent": len(issues) == 0,
            "issues": issues,
        }
