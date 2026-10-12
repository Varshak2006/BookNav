"""
FAISS Vector Search Module — Configuration.

Centralizes all parameters for FAISS index construction, search behavior,
persistence paths, and embedding models.
"""

import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent  # e:\BookNav-master\server
FAISS_DATA_DIR = Path(
    os.environ.get("FAISS_DATA_DIR", str(BASE_DIR / "faiss_data"))
)
INDEX_FILENAME = os.environ.get("FAISS_INDEX_FILE", "book_vectors.index")
MAPPING_FILENAME = os.environ.get("FAISS_MAPPING_FILE", "book_id_mapping.json")
METADATA_FILENAME = os.environ.get("FAISS_METADATA_FILE", "index_metadata.json")

INDEX_PATH = FAISS_DATA_DIR / INDEX_FILENAME
MAPPING_PATH = FAISS_DATA_DIR / MAPPING_FILENAME
METADATA_PATH = FAISS_DATA_DIR / METADATA_FILENAME

# Embedding Model Configuration
# Standard SBERT model: all-MiniLM-L6-v2 outputs 384-dimensional dense vectors
SBERT_MODEL_NAME = os.environ.get(
    "SBERT_MODEL_NAME", "all-MiniLM-L6-v2"
)
EMBEDDING_DIM = int(os.environ.get("FAISS_EMBEDDING_DIM", "384"))

# Distance Metric: "IP" (Inner Product with L2 normalization = Cosine Similarity) or "L2"
DISTANCE_METRIC = os.environ.get("FAISS_DISTANCE_METRIC", "IP").upper()

# Index Type: "FLAT" (exact), "IVF" (inverted file), "HNSW" (hierarchical navigable small world)
INDEX_TYPE = os.environ.get("FAISS_INDEX_TYPE", "FLAT").upper()

# Search Defaults
DEFAULT_TOP_K = int(os.environ.get("FAISS_DEFAULT_TOP_K", "10"))
MAX_TOP_K = int(os.environ.get("FAISS_MAX_TOP_K", "100"))

# Candidate pool expansion multiplier when applying post-retrieval metadata filters
CANDIDATE_EXPANSION_FACTOR = int(os.environ.get("FAISS_CANDIDATE_EXPANSION_FACTOR", "5"))

# ANN (IVF / HNSW) Tunables
IVF_NLIST = int(os.environ.get("FAISS_IVF_NLIST", "16"))       # Number of clusters
IVF_NPROBE = int(os.environ.get("FAISS_IVF_NPROBE", "4"))      # Clusters searched per query
HNSW_M = int(os.environ.get("FAISS_HNSW_M", "16"))             # Number of neighbors per node
HNSW_EF_CONSTRUCTION = int(os.environ.get("FAISS_HNSW_EF_CONSTRUCTION", "64"))
HNSW_EF_SEARCH = int(os.environ.get("FAISS_HNSW_EF_SEARCH", "32"))

# MongoDB Connection (for standalone python index builder)
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/book")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "book")
MONGO_COLLECTION_NAME = os.environ.get("MONGO_COLLECTION_NAME", "books")
