"""
FAISS Vector Search Module — Index Builder Script.

Reads books from MongoDB, formats textual representations, generates
Sentence-BERT embeddings, constructs the FAISS index with ID mapping,
and saves the index artifacts atomically to disk.
"""

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

from pymongo import MongoClient

from .config import (
    DISTANCE_METRIC,
    EMBEDDING_DIM,
    INDEX_PATH,
    INDEX_TYPE,
    MAPPING_PATH,
    METADATA_PATH,
    MONGO_COLLECTION_NAME,
    MONGO_DB_NAME,
    MONGO_URI,
    SBERT_MODEL_NAME,
)
from .embedding_adapter import EmbeddingAdapter
from .id_mapping import IdMappingManager
from .index_manager import IndexManager
from .index_metadata import IndexMetadata


def fetch_books_from_mongo(
    uri: str = MONGO_URI,
    db_name: str = MONGO_DB_NAME,
    collection_name: str = MONGO_COLLECTION_NAME,
) -> List[Dict[str, Any]]:
    """Fetch all books from MongoDB."""
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    db = client[db_name]
    collection = db[collection_name]
    cursor = collection.find({})
    books = []
    for doc in cursor:
        doc["_id"] = str(doc["_id"])
        books.append(doc)
    client.close()
    return books


def build_index_from_books(
    books: List[Dict[str, Any]],
    index_type: str = INDEX_TYPE,
    metric: str = DISTANCE_METRIC,
    model_name: str = SBERT_MODEL_NAME,
    index_path: Path = INDEX_PATH,
    mapping_path: Path = MAPPING_PATH,
    metadata_path: Path = METADATA_PATH,
    batch_size: int = 64,
    allow_empty: bool = False,
) -> Dict[str, Any]:
    """
    Build FAISS index and ID mapping from a list of book dictionaries safely.

    Uses staging-based coordinated persistence:
    1. Rejects 0-book rebuilds unless allow_empty=True is explicitly set.
    2. Builds new artifacts into temporary staging files (.tmp_build).
    3. Validates all temporary artifacts against dimension, count, and ID consistency.
    4. Backs up existing valid artifacts to .prev.
    5. Atomically replaces active artifacts with the validated generation.
    """
    import shutil
    from faiss_engine.validator import validate_index_artifacts

    start_time = time.perf_counter()

    if not books and not allow_empty:
        raise ValueError(
            "Index build aborted: 0 books provided. Refusing to overwrite active index "
            "with an empty generation without explicit allow_empty=True authorization."
        )

    logger.info("Initializing EmbeddingAdapter with model '%s'...", model_name)
    adapter = EmbeddingAdapter(model_name=model_name)

    logger.info("Formatting book metadata texts...")
    texts = [adapter.format_book_text(b) for b in books]

    logger.info("Generating SBERT embeddings for %d books (batch_size=%d)...", len(texts), batch_size)
    embed_start = time.perf_counter()
    vectors = adapter.encode_documents(texts, batch_size=batch_size, normalize=(metric == "IP"))
    embed_duration = time.perf_counter() - embed_start
    logger.info("Generated %d vectors in %.2fs.", len(vectors), embed_duration)

    dim = vectors.shape[1] if len(vectors) > 0 else EMBEDDING_DIM

    # Staging paths
    tmp_index_path = index_path.with_suffix(".tmp_build")
    tmp_mapping_path = mapping_path.with_suffix(".tmp_build")
    tmp_metadata_path = metadata_path.with_suffix(".tmp_build")

    index_mgr = IndexManager(
        dimension=dim,
        metric=metric,
        index_type=index_type,
        index_path=tmp_index_path,
    )
    index_mgr.build_empty_index(use_id_map=True)

    mapping_mgr = IdMappingManager(mapping_path=tmp_mapping_path)
    mapping_mgr.clear()

    # Register books in mapping manager
    ids = []
    for book in books:
        mid = str(book["_id"])
        meta = {
            "title": book.get("title", ""),
            "author": book.get("author", ""),
            "category": book.get("category", ""),
            "description": book.get("description", ""),
            "shelf": book.get("shelf", ""),
            "rack": book.get("rack", ""),
            "location": book.get("location", ""),
            "keywords": book.get("keywords", ""),
        }
        fid = mapping_mgr.add_entry(mid, meta)
        ids.append(fid)

    if len(vectors) > 0:
        logger.info("Adding %d vectors to FAISS index...", len(vectors))
        index_mgr.add_vectors(vectors, ids=ids)

    # Coordinated generation identifier
    generation_id = IndexMetadata.create_generation_id()
    mapping_mgr.generation_id = generation_id

    # Create metadata in staging
    meta_mgr = IndexMetadata(metadata_path=tmp_metadata_path)
    meta_mgr.set(
        generation_id=generation_id,
        model_name=model_name,
        embedding_dim=dim,
        distance_metric=metric,
        index_type=index_type,
        vector_count=index_mgr.count,
    )

    logger.info("Saving temporary build artifacts...")
    index_mgr.save(tmp_index_path)
    mapping_mgr.save()
    meta_mgr.save()

    # Pre-activation validation
    logger.info("Validating newly built artifacts before activation...")
    validation = validate_index_artifacts(
        index_path=tmp_index_path,
        mapping_path=tmp_mapping_path,
        metadata_path=tmp_metadata_path,
        expected_model=model_name,
        expected_dim=dim,
        expected_metric=metric,
        expected_index_type=index_type,
    )

    if not validation["valid"]:
        # Clean up temporary build files
        for p in (tmp_index_path, tmp_mapping_path, tmp_metadata_path):
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass
        raise RuntimeError(
            f"Pre-activation index validation failed ({validation['status_code']}): "
            f"{'; '.join(validation['errors'])}. Active index left untouched."
        )

    # Preserve previous generation backups
    for orig in (index_path, mapping_path, metadata_path):
        if orig.exists():
            backup_path = orig.with_suffix(".prev")
            try:
                shutil.copy2(orig, backup_path)
            except Exception as copy_err:
                logger.warning("Could not create backup for %s: %s", orig, copy_err)

    # Atomic activation
    logger.info("Activating new index generation %s...", generation_id)
    os.replace(tmp_index_path, index_path)
    os.replace(tmp_mapping_path, mapping_path)
    os.replace(tmp_metadata_path, metadata_path)
    logger.info("Generation %s activated successfully.", generation_id)

    total_duration = time.perf_counter() - start_time
    file_size_bytes = index_path.stat().st_size if index_path.exists() else 0

    stats = {
        "total_books": len(books),
        "vectors_indexed": index_mgr.count,
        "embedding_dim": dim,
        "index_type": index_type,
        "metric": metric,
        "generation_id": generation_id,
        "index_file_size_bytes": file_size_bytes,
        "embedding_time_sec": round(embed_duration, 3),
        "total_build_time_sec": round(total_duration, 3),
    }

    logger.info("Index build complete in %.2fs:", total_duration)
    for k, v in stats.items():
        logger.info("  %s: %s", k, v)

    return stats


def main():
    parser = argparse.ArgumentParser(description="Build BookNav FAISS Vector Index")
    parser.add_argument("--mongo_uri", default=MONGO_URI, help="MongoDB connection URI")
    parser.add_argument("--db_name", default=MONGO_DB_NAME, help="MongoDB database name")
    parser.add_argument("--collection", default=MONGO_COLLECTION_NAME, help="Collection name")
    parser.add_argument("--index_type", default=INDEX_TYPE, help="FLAT, IVF, or HNSW")
    parser.add_argument("--metric", default=DISTANCE_METRIC, help="IP or L2")
    parser.add_argument("--model", default=SBERT_MODEL_NAME, help="SBERT model identifier")
    args = parser.parse_args()

    # When run as __main__, configure logging to stderr so stdout is never polluted
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stderr,
    )

    logger.info("Connecting to MongoDB at %s...", args.mongo_uri)
    try:
        books = fetch_books_from_mongo(
            uri=args.mongo_uri,
            db_name=args.db_name,
            collection_name=args.collection,
        )
        logger.info("Retrieved %d books from MongoDB.", len(books))
    except Exception as exc:
        logger.error("Error fetching books from MongoDB: %s", exc)
        sys.exit(1)

    build_index_from_books(
        books=books,
        index_type=args.index_type,
        metric=args.metric,
        model_name=args.model,
    )


if __name__ == "__main__":
    main()
