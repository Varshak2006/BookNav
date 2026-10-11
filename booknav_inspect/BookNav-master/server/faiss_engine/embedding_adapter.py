"""
FAISS Vector Search Module - Embedding Adapter.

Provides a thin interface to Sentence-BERT for generating embeddings.
This adapter exists to isolate the FAISS module from the embedding
generation module that a teammate is building.

When the teammate's module is ready, this adapter can be replaced or
extended to delegate to their interface.  Until then, it loads the
configured SBERT model directly.

IMPORTANT:
- This does NOT replace the teammate's Embedding Generation Module.
- It uses the same model and configuration they are expected to use.
- Only one model instance is loaded (singleton pattern).
"""

from __future__ import annotations

import logging
import numpy as np
from typing import List, Optional, Union

from . import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton model holder
# ---------------------------------------------------------------------------

_model = None
_model_name: Optional[str] = None


def _load_model():
    """Load the SBERT model once (lazy singleton)."""
    global _model, _model_name

    if _model is not None and _model_name == config.SBERT_MODEL_NAME:
        return _model

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise ImportError(
            "sentence-transformers is required for embedding generation. "
            "Install it with: pip install sentence-transformers"
        ) from exc

    logger.info("Loading SBERT model: %s", config.SBERT_MODEL_NAME)
    _model = SentenceTransformer(config.SBERT_MODEL_NAME)
    _model_name = config.SBERT_MODEL_NAME

    # Verify dimension matches configuration
    test_vec = _model.encode(["test"], convert_to_numpy=True)
    actual_dim = test_vec.shape[1]
    if actual_dim != config.EMBEDDING_DIM:
        raise ValueError(
            f"Model '{config.SBERT_MODEL_NAME}' produces {actual_dim}-dim "
            f"embeddings, but FAISS_EMBEDDING_DIM is set to {config.EMBEDDING_DIM}. "
            f"Update FAISS_EMBEDDING_DIM or change the model."
        )

    logger.info(
        "SBERT model loaded: %s (dim=%d)", config.SBERT_MODEL_NAME, actual_dim
    )
    return _model


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def encode_texts(texts: List[str], normalize: bool = True) -> np.ndarray:
    """
    Encode a list of text strings into embedding vectors.

    Parameters
    ----------
    texts : list[str]
        The texts to encode.
    normalize : bool
        If True, L2-normalise each vector so that inner-product
        equals cosine similarity.  Should always be True when using
        IndexFlatIP.

    Returns
    -------
    np.ndarray
        2-D float32 array of shape (len(texts), EMBEDDING_DIM).
    """
    if not texts:
        return np.empty((0, config.EMBEDDING_DIM), dtype=np.float32)

    model = _load_model()
    embeddings = model.encode(
        texts,
        convert_to_numpy=True,
        show_progress_bar=False,
        normalize_embeddings=normalize,
    )

    return embeddings.astype(np.float32)


def encode_query(query: str, normalize: bool = True) -> np.ndarray:
    """
    Encode a single query string.

    Returns
    -------
    np.ndarray
        1-D float32 array of shape (EMBEDDING_DIM,).
    """
    if not query or not query.strip():
        raise ValueError("Query text must be a non-empty string.")

    vec = encode_texts([query.strip()], normalize=normalize)
    return vec[0]


def build_document_text(book: dict) -> str:
    """
    Construct the text representation of a book used for embedding.

    Concatenates the most semantically meaningful fields from the
    book metadata so that the embedding captures the book's content.
    """
    parts = []
    for field in ("title", "author", "category", "keywords", "description"):
        value = (book.get(field) or "").strip()
        if value:
            parts.append(value)
    return " ".join(parts)


def get_model_info() -> dict:
    """Return information about the currently loaded model."""
    model = _load_model()
    return {
        "model_name": config.SBERT_MODEL_NAME,
        "embedding_dim": config.EMBEDDING_DIM,
        "max_seq_length": getattr(model, "max_seq_length", None),
    }
