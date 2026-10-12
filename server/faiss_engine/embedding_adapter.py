"""
FAISS Vector Search Module — Sentence-BERT Embedding Adapter.

Integrates with Sentence-BERT for generating document and query embeddings.
Designed to cleanly accept the teammate's Embedding Generation Module
while providing a fallback to sentence-transformers 'all-MiniLM-L6-v2'.
"""

from typing import Any, Callable, Dict, List, Optional
import numpy as np

from .config import EMBEDDING_DIM, SBERT_MODEL_NAME
from .validator import normalize_vectors, validate_vector


class EmbeddingAdapter:
    """
    Adapter between BookNav's FAISS module and Sentence-BERT models.
    Supports lazy model loading and dependency injection for custom teammate modules.
    """

    def __init__(
        self,
        model_name: str = SBERT_MODEL_NAME,
        expected_dim: int = EMBEDDING_DIM,
        external_encoder: Optional[Callable[[List[str]], np.ndarray]] = None,
    ):
        self.model_name = model_name
        self.expected_dim = expected_dim
        self._external_encoder = external_encoder
        self._model: Any = None

    def set_external_encoder(self, encoder_fn: Callable[[List[str]], np.ndarray], dimension: Optional[int] = None):
        """
        Inject teammate's embedding function.
        Must accept a list of strings and return a 2D numpy array of embeddings.
        """
        self._external_encoder = encoder_fn
        if dimension is not None:
            self.expected_dim = dimension

    def _get_model(self):
        """Lazy load SentenceTransformer model if no external encoder is provided."""
        if self._model is None and self._external_encoder is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to load SentenceTransformer model '{self.model_name}': {exc}"
                ) from exc
        return self._model

    @staticmethod
    def format_book_text(book: Dict[str, Any]) -> str:
        """
        Construct a dense semantic representation text from book metadata.
        Uses title, author, category, keywords, and description.
        """
        parts = []
        title = (book.get("title") or "").strip()
        author = (book.get("author") or "").strip()
        category = (book.get("category") or "").strip()
        keywords = (book.get("keywords") or "").strip()
        description = (book.get("description") or "").strip()

        if title:
            parts.append(f"Title: {title}")
        if author:
            parts.append(f"Author: {author}")
        if category:
            parts.append(f"Category: {category}")
        if keywords:
            parts.append(f"Keywords: {keywords}")
        if description:
            parts.append(f"Description: {description}")

        return " | ".join(parts) if parts else "Untitled Book"

    def encode_query(self, query: str, normalize: bool = True) -> np.ndarray:
        """
        Generate embedding for a single user query string.

        Returns:
            np.ndarray: 1D float32 array of shape (expected_dim,).
        """
        if not query or not query.strip():
            raise ValueError("Query string cannot be empty.")

        clean_query = query.strip()
        if self._external_encoder is not None:
            vecs = self._external_encoder([clean_query])
            vec = np.asarray(vecs[0], dtype=np.float32)
        else:
            model = self._get_model()
            vec = model.encode(clean_query, convert_to_numpy=True, show_progress_bar=False)
            vec = np.asarray(vec, dtype=np.float32)

        vec = validate_vector(vec, self.expected_dim, allow_batch=False)
        if normalize:
            vec = normalize_vectors(vec)
        return vec

    def encode_documents(self, texts: List[str], batch_size: int = 64, normalize: bool = True) -> np.ndarray:
        """
        Generate embeddings for a list of document texts.

        Returns:
            np.ndarray: 2D float32 array of shape (N, expected_dim).
        """
        if not texts:
            return np.empty((0, self.expected_dim), dtype=np.float32)

        if self._external_encoder is not None:
            vecs = self._external_encoder(texts)
            arr = np.asarray(vecs, dtype=np.float32)
        else:
            model = self._get_model()
            arr = model.encode(
                texts,
                batch_size=batch_size,
                convert_to_numpy=True,
                show_progress_bar=False
            )
            arr = np.asarray(arr, dtype=np.float32)

        arr = validate_vector(arr, self.expected_dim, allow_batch=True)
        if normalize:
            arr = normalize_vectors(arr)
        return arr
