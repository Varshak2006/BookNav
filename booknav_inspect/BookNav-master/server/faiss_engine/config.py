"""
FAISS Vector Search Module - Configuration.

Centralizes all tunable parameters for index construction,
search behaviour, and persistence paths.  Values can be
overridden via environment variables where documented.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent          # server/
FAISS_DATA_DIR = Path(
    os.environ.get("FAISS_DATA_DIR", str(BASE_DIR / "faiss_data"))
)
INDEX_FILENAME = os.environ.get("FAISS_INDEX_FILE", "book_vectors.index")
MAPPING_FILENAME = os.environ.get("FAISS_MAPPING_FILE", "book_id_mapping.json")

INDEX_PATH = FAISS_DATA_DIR / INDEX_FILENAME
MAPPING_PATH = FAISS_DATA_DIR / MAPPING_FILENAME

# ---------------------------------------------------------------------------
# Embedding model
# ---------------------------------------------------------------------------

# Default SBERT model - must match what the Embedding Generation Module uses.
SBERT_MODEL_NAME = os.environ.get(
    "SBERT_MODEL_NAME", "all-MiniLM-L6-v2"
)

# Expected embedding dimension for the default model.
# Validated at index-load time; override only if a different model is used.
EMBEDDING_DIM = int(os.environ.get("FAISS_EMBEDDING_DIM", "384"))

# ---------------------------------------------------------------------------
# FAISS index
# ---------------------------------------------------------------------------

# Distance metric used for the flat index.
# "IP" -> inner-product (cosine similarity when vectors are L2-normalised).
# "L2" -> squared Euclidean distance.
DISTANCE_METRIC = os.environ.get("FAISS_DISTANCE_METRIC", "IP")

# ---------------------------------------------------------------------------
# Search defaults
# ---------------------------------------------------------------------------

DEFAULT_TOP_K = int(os.environ.get("FAISS_DEFAULT_TOP_K", "10"))
MAX_TOP_K = int(os.environ.get("FAISS_MAX_TOP_K", "100"))

# When metadata filters are applied after FAISS retrieval, we request
# more candidates than the final top-k to compensate for filtered-out
# results.  CANDIDATE_EXPANSION_FACTOR * top_k = initial FAISS request.
CANDIDATE_EXPANSION_FACTOR = int(
    os.environ.get("FAISS_CANDIDATE_EXPANSION", "3")
)

# Maximum number of expansion rounds before giving up when filters
# are too restrictive.
MAX_EXPANSION_ROUNDS = int(
    os.environ.get("FAISS_MAX_EXPANSION_ROUNDS", "3")
)

# ---------------------------------------------------------------------------
# MongoDB (used only by the index-builder when fetching book metadata)
# ---------------------------------------------------------------------------

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/book")
