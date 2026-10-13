"""
BookNav FAISS Vector Search Module package.
"""

from .config import (
    DISTANCE_METRIC,
    EMBEDDING_DIM,
    INDEX_PATH,
    INDEX_TYPE,
    MAPPING_PATH,
    METADATA_PATH,
    SBERT_MODEL_NAME,
)
from .embedding_adapter import EmbeddingAdapter
from .id_mapping import IdMappingManager
from .index_manager import IndexManager
from .search_service import SearchService
from .validator import VectorValidationError, normalize_vectors, validate_vector

__all__ = [
    "DISTANCE_METRIC",
    "EMBEDDING_DIM",
    "INDEX_PATH",
    "INDEX_TYPE",
    "MAPPING_PATH",
    "METADATA_PATH",
    "SBERT_MODEL_NAME",
    "EmbeddingAdapter",
    "IdMappingManager",
    "IndexManager",
    "SearchService",
    "VectorValidationError",
    "normalize_vectors",
    "validate_vector",
]
