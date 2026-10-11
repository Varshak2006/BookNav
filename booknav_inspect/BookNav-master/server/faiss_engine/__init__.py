"""FAISS Vector Search Engine for BookNav."""

from .faiss_search import FAISSSearchService, IDMapping, validate_vector
from .embedding_adapter import encode_query, encode_texts, build_document_text, get_model_info
from . import config
