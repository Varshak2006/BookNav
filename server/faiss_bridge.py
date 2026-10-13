"""
FAISS Vector Search Module — Python IPC Bridge.

Communicates with the Node.js Express backend over standard JSON-lines IPC
(stdin / stdout). Keeps the FAISS index and SBERT model resident in memory
to eliminate cold-start latency.

Enforces strict readiness validation:
- Distinguishes missing, corrupted, model mismatch, dimension mismatch,
  metric mismatch, count mismatch, generation mismatch, and intentional empty index.
- Never silently substitutes an empty index for a failed production index.
- Never overwrites a valid index on error.
- Provides controlled recovery and validation actions.
"""

import json
import logging
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Dict

# Add server directory to path
SERVER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SERVER_DIR))

from faiss_engine.config import (
    DISTANCE_METRIC,
    EMBEDDING_DIM,
    INDEX_PATH,
    INDEX_TYPE,
    MAPPING_PATH,
    METADATA_PATH,
    SBERT_MODEL_NAME,
)
from faiss_engine.embedding_adapter import EmbeddingAdapter
from faiss_engine.id_mapping import IdMappingManager
from faiss_engine.index_manager import IndexManager
from faiss_engine.index_metadata import IndexMetadata
from faiss_engine.search_service import SearchService
from faiss_engine.validator import (
    IndexNotReadyError,
    IndexReadinessState,
    validate_index_artifacts,
)

# Initialize components
id_mapping = IdMappingManager(mapping_path=MAPPING_PATH)
index_manager = IndexManager(
    dimension=EMBEDDING_DIM,
    metric=DISTANCE_METRIC,
    index_type=INDEX_TYPE,
    index_path=INDEX_PATH,
)
index_meta = IndexMetadata(metadata_path=METADATA_PATH)

# Lazy embedding adapter
embedding_adapter = EmbeddingAdapter(
    model_name=SBERT_MODEL_NAME,
    expected_dim=EMBEDDING_DIM,
)


def evaluate_readiness() -> Dict[str, Any]:
    """Check readiness against on-disk artifacts and active configuration."""
    allow_empty = os.environ.get("ALLOW_EMPTY_INDEX", "").lower() in ("1", "true")
    return validate_index_artifacts(
        index_path=INDEX_PATH,
        mapping_path=MAPPING_PATH,
        metadata_path=METADATA_PATH,
        expected_dim=EMBEDDING_DIM,
        expected_metric=DISTANCE_METRIC,
        expected_model=SBERT_MODEL_NAME,
        expected_type=INDEX_TYPE,
        allow_empty=allow_empty,
    )


# Initial readiness evaluation
readiness = evaluate_readiness()
if readiness["ready"]:
    if readiness["state"] == IndexReadinessState.INTENTIONALLY_EMPTY:
        index_manager.build_empty_index(use_id_map=True)
        id_mapping.clear()
    else:
        id_mapping.load()
        index_manager.load()
        index_meta.load()
else:
    # Log specific cause to stderr; DO NOT overwrite with an empty index
    sys.stderr.write(f"FAISS index not ready on initialization: [{readiness['state']}] {readiness['reason']}\n")
    sys.stderr.flush()

search_service = SearchService(
    index_manager=index_manager,
    id_mapping=id_mapping,
    embedding_adapter=embedding_adapter,
    readiness_checker=evaluate_readiness,
)


def handle_search(payload: dict) -> dict:
    current_readiness = evaluate_readiness()
    if not current_readiness["ready"]:
        raise IndexNotReadyError(
            state=current_readiness["state"],
            reason=current_readiness["reason"],
            details=current_readiness.get("details"),
        )

    query = payload.get("query")
    top_k = payload.get("top_k", 10)
    filters = payload.get("filters", {})
    candidate_expansion = payload.get("candidate_expansion")
    min_score = payload.get("min_score")
    return search_service.search(
        query=query,
        top_k=top_k,
        filters=filters,
        candidate_expansion=candidate_expansion,
        min_score=min_score,
    )


def handle_add_book(payload: dict) -> dict:
    book = payload.get("book", {})
    book_id = str(book.get("_id") or book.get("id", ""))
    if not book_id:
        raise ValueError("Book must include a valid '_id' or 'id'.")

    # Format text and encode
    text = embedding_adapter.format_book_text(book)
    vector = embedding_adapter.encode_query(text, normalize=(index_manager.metric == "IP"))

    # Ensure index is initialized
    if not index_manager.is_initialized:
        index_manager.build_empty_index(use_id_map=True)

    # Check if book already exists — if so, remove old vector first to prevent duplicates
    existing_fid = id_mapping.get_faiss_id(book_id)
    if existing_fid is not None:
        index_manager.remove_ids([existing_fid])

    # Register in ID mapping (reuses existing fid if book already exists)
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
    fid = id_mapping.add_entry(book_id, meta)

    # Add to FAISS index with explicit ID
    index_manager.add_vectors(vector.reshape(1, -1), ids=[fid])

    # Persist atomically
    index_manager.save()
    id_mapping.save()

    gen_id = id_mapping.generation_id or index_meta.generation_id or IndexMetadata.create_generation_id()
    id_mapping.generation_id = gen_id
    id_mapping.save()

    index_meta.set(
        generation_id=gen_id,
        model_name=embedding_adapter.model_name,
        embedding_dim=index_manager.dimension,
        distance_metric=index_manager.metric,
        index_type=index_manager.index_type,
        vector_count=index_manager.count,
    )
    index_meta.save()

    return {
        "success": True,
        "book_id": book_id,
        "faiss_id": fid,
        "total_indexed": index_manager.count,
    }


def handle_delete_book(payload: dict) -> dict:
    book_id = str(payload.get("book_id") or payload.get("id", ""))
    if not book_id:
        raise ValueError("Must provide book_id to delete.")

    fid = id_mapping.remove_by_mongo_id(book_id)
    if fid is not None:
        index_manager.remove_ids([fid])
        index_manager.save()
        id_mapping.save()

        gen_id = id_mapping.generation_id or index_meta.generation_id or IndexMetadata.create_generation_id()
        index_meta.set(
            generation_id=gen_id,
            model_name=embedding_adapter.model_name,
            embedding_dim=index_manager.dimension,
            distance_metric=index_manager.metric,
            index_type=index_manager.index_type,
            vector_count=index_manager.count,
        )
        index_meta.save()
        return {
            "success": True,
            "book_id": book_id,
            "removed_faiss_id": fid,
            "total_indexed": index_manager.count,
        }
    return {
        "success": False,
        "message": f"Book ID '{book_id}' not found in index mapping.",
        "total_indexed": index_manager.count,
    }


def handle_rebuild(payload: dict) -> dict:
    from faiss_engine.build_index import build_index_from_books, fetch_books_from_mongo

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stderr,
    )

    books = payload.get("books")
    if books is None:
        books = fetch_books_from_mongo()

    allow_empty = payload.get("allow_empty", False)
    stats = build_index_from_books(
        books=books,
        index_type=payload.get("index_type", INDEX_TYPE),
        metric=payload.get("metric", DISTANCE_METRIC),
        model_name=payload.get("model", SBERT_MODEL_NAME),
        allow_empty=allow_empty,
    )

    # Reload validated artifacts into active memory
    id_mapping.load()
    index_manager.load()
    index_meta.load()

    return {
        "success": True,
        "stats": stats,
    }


def handle_recover() -> dict:
    from faiss_engine.build_index import restore_previous_generation

    restored = restore_previous_generation()
    if restored:
        id_mapping.load()
        index_manager.load()
        index_meta.load()
        new_readiness = evaluate_readiness()
        return {
            "success": True,
            "message": "Restored previous generation from backup.",
            "readiness": new_readiness,
        }
    return {
        "success": False,
        "message": "Failed to restore: backup artifacts missing or unreadable.",
    }


def handle_status() -> dict:
    file_size = INDEX_PATH.stat().st_size if INDEX_PATH.exists() else 0
    vec_count = index_manager.count
    map_count = len(id_mapping)
    current_readiness = evaluate_readiness()

    # Health issues check
    health_issues = []
    if not current_readiness["ready"]:
        health_issues.append(f"Not ready [{current_readiness['state']}]: {current_readiness['reason']}")
    if vec_count != map_count:
        health_issues.append(
            f"Count mismatch: index has {vec_count} vectors, mapping has {map_count} entries."
        )
    if not index_manager.is_initialized:
        health_issues.append("Index is not initialized in memory.")

    generation_info = {
        "generation_id": index_meta.generation_id,
        "mapping_generation_id": id_mapping.generation_id,
        "generations_match": (index_meta.generation_id == id_mapping.generation_id),
    }

    return {
        "initialized": index_manager.is_initialized,
        "ready": current_readiness["ready"],
        "readiness_state": current_readiness["state"],
        "readiness_reason": current_readiness["reason"],
        "vectors_indexed": vec_count,
        "mapping_count": map_count,
        "counts_match": (vec_count == map_count),
        "dimension": index_manager.dimension,
        "metric": index_manager.metric,
        "index_type": index_manager.index_type,
        "index_file_size_bytes": file_size,
        "model_name": embedding_adapter.model_name,
        "generation": generation_info,
        "health_issues": health_issues,
        "healthy": len(health_issues) == 0 and current_readiness["ready"],
    }


def process_message(line: str) -> str:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError as exc:
        return json.dumps({"ok": False, "error": f"Invalid JSON input: {exc}"})

    req_id = payload.get("id")
    action = payload.get("action", "search")

    try:
        if action == "search":
            data = handle_search(payload)
        elif action == "add_book":
            data = handle_add_book(payload)
        elif action == "delete_book":
            data = handle_delete_book(payload)
        elif action == "update_book":
            data = handle_add_book(payload)
        elif action == "rebuild":
            data = handle_rebuild(payload)
        elif action == "recover":
            data = handle_recover()
        elif action == "validate":
            data = evaluate_readiness()
        elif action in ("status", "info"):
            data = handle_status()
        elif action in ("ping", "health"):
            cur_r = evaluate_readiness()
            data = {
                "status": "healthy" if cur_r["ready"] else "unhealthy",
                "ready": cur_r["ready"],
                "count": index_manager.count,
                "reason": cur_r["reason"],
            }
        else:
            return json.dumps({
                "id": req_id,
                "ok": False,
                "error": f"Unknown action: '{action}'"
            })

        return json.dumps({"id": req_id, "ok": True, "data": data}, ensure_ascii=False)
    except Exception as exc:
        sys.stderr.write(f"Error handling action '{action}': {traceback.format_exc()}\n")
        sys.stderr.flush()
        return json.dumps({
            "id": req_id,
            "ok": False,
            "error": str(exc),
            "state": getattr(exc, "state", "ERROR"),
        })


def main():
    initial_readiness = evaluate_readiness()
    if initial_readiness["ready"]:
        sys.stderr.write(f"FAISS_BRIDGE_READY {json.dumps(initial_readiness)}\n")
    else:
        sys.stderr.write(f"FAISS_BRIDGE_NOT_READY {json.dumps(initial_readiness)}\n")
    sys.stderr.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        response = process_message(line)
        print(response, flush=True)


if __name__ == "__main__":
    main()
