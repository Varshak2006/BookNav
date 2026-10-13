"""
FAISS Vector Search Module — Safe Index Builder Script.

Reads books from MongoDB, formats textual representations, generates
Sentence-BERT embeddings, constructs the FAISS index with ID mapping,
stages the artifacts, validates them completely before activation, and preserves
the previous valid generation for rollback safety.
"""

import argparse
import logging
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

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
from .validator import IndexReadinessState, validate_index_artifacts


def fetch_books_from_mongo(
    uri: str = MONGO_URI,
    db_name: str = MONGO_DB_NAME,
    collection_name: str = MONGO_COLLECTION_NAME,
) -> List[Dict[str, Any]]:
    """Fetch all books from MongoDB safely."""
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


def restore_previous_generation(
    index_path: Path = INDEX_PATH,
    mapping_path: Path = MAPPING_PATH,
    metadata_path: Path = METADATA_PATH,
) -> bool:
    """
    Restore index from .prev backup files if available.
    Returns True if successfully restored, False otherwise.
    """
    prev_index = index_path.with_name(f"{index_path.name}.prev")
    prev_mapping = mapping_path.with_name(f"{mapping_path.name}.prev")
    prev_metadata = metadata_path.with_name(f"{metadata_path.name}.prev")

    if not (prev_index.exists() and prev_mapping.exists() and prev_metadata.exists()):
        logger.error("Cannot restore: .prev backup files are missing or incomplete.")
        return False

    try:
        shutil.copy2(prev_index, index_path)
        shutil.copy2(prev_mapping, mapping_path)
        shutil.copy2(prev_metadata, metadata_path)
        logger.info("Successfully restored previous generation from .prev backups.")
        return True
    except Exception as exc:
        logger.error("Failed to restore previous generation: %s", exc)
        return False


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
    Build FAISS index and ID mapping from a list of book dictionaries.

    Safe Rebuild Guarantees:
    1. Rejects empty rebuilds unless allow_empty is explicitly True.
    2. Constructs artifacts in staged (.staged) files first.
    3. Validates staged artifacts before replacing active files.
    4. Preserves previous generation as (.prev) backup files.
    5. Replaces active files atomically only upon 100% validation pass.
    """
    start_time = time.perf_counter()

    if not books or len(books) == 0:
        if not allow_empty:
            raise ValueError(
                "Safe Rebuild Rejected: Received 0 books from MongoDB and empty rebuild was not authorized. "
                "Preserving existing populated index."
            )
        logger.warning("Empty rebuild explicitly authorized. An empty index will be constructed.")

    # Target staging paths
    staged_index = index_path.with_name(f"{index_path.name}.staged")
    staged_mapping = mapping_path.with_name(f"{mapping_path.name}.staged")
    staged_metadata = metadata_path.with_name(f"{metadata_path.name}.staged")

    staged_index.parent.mkdir(parents=True, exist_ok=True)

    try:
        logger.info("Initializing EmbeddingAdapter with model '%s'...", model_name)
        adapter = EmbeddingAdapter(model_name=model_name)

        logger.info("Formatting book metadata texts for %d books...", len(books))
        texts = [adapter.format_book_text(b) for b in books]

        logger.info("Generating SBERT embeddings for %d books (batch_size=%d)...", len(texts), batch_size)
        embed_start = time.perf_counter()
        vectors = adapter.encode_documents(texts, batch_size=batch_size, normalize=(metric == "IP"))
        embed_duration = time.perf_counter() - embed_start
        logger.info("Generated %d vectors in %.2fs.", len(vectors), embed_duration)

        dim = vectors.shape[1] if len(vectors) > 0 else EMBEDDING_DIM
        staged_index_mgr = IndexManager(
            dimension=dim,
            metric=metric,
            index_type=index_type,
            index_path=staged_index,
        )
        staged_index_mgr.build_empty_index(use_id_map=True)

        staged_mapping_mgr = IdMappingManager(mapping_path=staged_mapping)
        staged_mapping_mgr.clear()

        # Register books in staged mapping manager
        ids = []
        for book in books:
            mid = str(book.get("_id") or book.get("id"))
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
            fid = staged_mapping_mgr.add_entry(mid, meta)
            ids.append(fid)

        if len(vectors) > 0:
            logger.info("Adding %d vectors to staged FAISS index...", len(vectors))
            staged_index_mgr.add_vectors(vectors, ids=ids)

        # Coordinate generation identifier
        generation_id = IndexMetadata.create_generation_id()
        staged_mapping_mgr.generation_id = generation_id

        staged_meta_mgr = IndexMetadata(metadata_path=staged_metadata)
        staged_meta_mgr.set(
            generation_id=generation_id,
            model_name=model_name,
            embedding_dim=dim,
            distance_metric=metric,
            index_type=index_type,
            vector_count=staged_index_mgr.count,
        )

        # Persist to staged files
        logger.info("Writing staged FAISS index to %s...", staged_index)
        staged_index_mgr.save()
        logger.info("Writing staged ID mapping to %s...", staged_mapping)
        staged_mapping_mgr.save()
        logger.info("Writing staged metadata to %s...", staged_metadata)
        staged_meta_mgr.save()

        # --- VALIDATE STAGED ARTIFACTS BEFORE PROMOTION ---
        logger.info("Validating staged artifacts...")
        validation = validate_index_artifacts(
            index_path=staged_index,
            mapping_path=staged_mapping,
            metadata_path=staged_metadata,
            expected_dim=dim,
            expected_metric=metric,
            expected_model=model_name,
            expected_type=index_type,
            allow_empty=allow_empty,
        )

        if not validation["ready"]:
            raise RuntimeError(
                f"Staged index validation failed [{validation['state']}]: {validation['reason']}"
            )

        # --- PRESERVE CURRENT GENERATION AS BACKUP ---
        prev_index = index_path.with_name(f"{index_path.name}.prev")
        prev_mapping = mapping_path.with_name(f"{mapping_path.name}.prev")
        prev_metadata = metadata_path.with_name(f"{metadata_path.name}.prev")

        if index_path.exists():
            shutil.copy2(index_path, prev_index)
        if mapping_path.exists():
            shutil.copy2(mapping_path, prev_mapping)
        if metadata_path.exists():
            shutil.copy2(metadata_path, prev_metadata)

        # --- ATOMICALLY PROMOTE STAGED ARTIFACTS TO ACTIVE ---
        logger.info("Promoting validated staged artifacts to active index...")
        os.replace(staged_index, index_path)
        os.replace(staged_mapping, mapping_path)
        os.replace(staged_metadata, metadata_path)

        total_duration = time.perf_counter() - start_time
        file_size_bytes = index_path.stat().st_size if index_path.exists() else 0

        stats = {
            "total_books": len(books),
            "vectors_indexed": staged_index_mgr.count,
            "embedding_dim": dim,
            "index_type": index_type,
            "metric": metric,
            "generation_id": generation_id,
            "index_file_size_bytes": file_size_bytes,
            "embedding_time_sec": round(embed_duration, 3),
            "total_build_time_sec": round(total_duration, 3),
            "validated": True,
            "status": "active",
        }

        logger.info("Index build & activation complete in %.2fs: %s", total_duration, stats)
        return stats

    except Exception as exc:
        # Clean up staged files on error to ensure clean state
        for p in (staged_index, staged_mapping, staged_metadata):
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass
        logger.error("Index rebuild aborted: %s", exc)
        raise


def main():
    parser = argparse.ArgumentParser(description="Build BookNav FAISS Vector Index Safely")
    parser.add_argument("--mongo_uri", default=MONGO_URI, help="MongoDB connection URI")
    parser.add_argument("--db_name", default=MONGO_DB_NAME, help="MongoDB database name")
    parser.add_argument("--collection", default=MONGO_COLLECTION_NAME, help="Collection name")
    parser.add_argument("--index_type", default=INDEX_TYPE, help="FLAT, IVF, or HNSW")
    parser.add_argument("--metric", default=DISTANCE_METRIC, help="IP or L2")
    parser.add_argument("--model", default=SBERT_MODEL_NAME, help="SBERT model identifier")
    parser.add_argument("--allow_empty", action="store_true", help="Authorize an empty rebuild")
    parser.add_argument("--restore_prev", action="store_true", help="Restore previous generation from backup")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stderr,
    )

    if args.restore_prev:
        success = restore_previous_generation()
        sys.exit(0 if success else 1)

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

    try:
        build_index_from_books(
            books=books,
            index_type=args.index_type,
            metric=args.metric,
            model_name=args.model,
            allow_empty=args.allow_empty,
        )
    except Exception as exc:
        logger.error("Failed to build index: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
