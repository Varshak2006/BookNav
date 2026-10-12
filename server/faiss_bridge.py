"""
FAISS Vector Search Module — Python IPC Bridge.

Communicates with the Node.js Express backend over standard JSON-lines IPC
(stdin / stdout). Keeps the FAISS index and SBERT model resident in memory
to eliminate cold-start latency.
"""

import json
import logging
import os
import sys
import traceback
from pathlib import Path

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
from faiss_engine.validator import validate_index_artifacts


# Global readiness state
readiness_state = {
    "ready": False,
    "status_code": "INITIALIZING",
    "errors": [],
    "details": {},
}

# Initialize component instances
id_mapping = IdMappingManager(mapping_path=MAPPING_PATH)
index_manager = IndexManager(
    dimension=EMBEDDING_DIM,
    metric=DISTANCE_METRIC,
    index_type=INDEX_TYPE,
    index_path=INDEX_PATH,
)
index_meta = IndexMetadata(metadata_path=METADATA_PATH)

# Embedding adapter
embedding_adapter = EmbeddingAdapter(
    model_name=SBERT_MODEL_NAME,
    expected_dim=EMBEDDING_DIM,
)

search_service = SearchService(
    index_manager=index_manager,
    id_mapping=id_mapping,
    embedding_adapter=embedding_adapter,
)


def check_and_load_artifacts() -> bool:
    """
    Validate all index artifacts on disk before loading into memory.
    If validation fails, does NOT substitute an empty index — marks service NOT READY.
    """
    global readiness_state

    validation = validate_index_artifacts(
        index_path=INDEX_PATH,
        mapping_path=MAPPING_PATH,
        metadata_path=METADATA_PATH,
        expected_model=SBERT_MODEL_NAME,
        expected_dim=EMBEDDING_DIM,
        expected_metric=DISTANCE_METRIC,
        expected_index_type=INDEX_TYPE,
    )

    if not validation["valid"]:
        readiness_state = {
            "ready": False,
            "status_code": validation["status_code"],
            "errors": validation["errors"],
            "details": validation.get("details", {}),
        }
        sys.stderr.write(
            f"FAISS index validation failed ({validation['status_code']}): "
            f"{'; '.join(validation['errors'])}\n"
        )
        sys.stderr.flush()
        return False

    # Validation passed — load the active artifacts safely into memory
    id_mapping.load()
    index_manager.load()
    index_meta.load()

    readiness_state = {
        "ready": True,
        "status_code": "READY",
        "errors": [],
        "details": validation.get("details", {}),
    }
    sys.stderr.write(
        f"FAISS index validated and loaded successfully ({index_manager.count} vectors, "
        f"dim={index_manager.dimension}, metric={index_manager.metric}).\n"
    )
    sys.stderr.flush()
    return True


# Run startup validation
check_and_load_artifacts()


def handle_search(payload: dict) -> dict:
    if not readiness_state["ready"]:
        raise RuntimeError(
            f"FAISS search service is not ready ({readiness_state['status_code']}): "
            f"{'; '.join(readiness_state['errors'])}"
        )

    query = payload.get("query")
    top_k = payload.get("top_k", 10)
    filters = payload.get("filters", {})
    candidate_expansion = payload.get("candidate_expansion")
    return search_service.search(
        query=query,
        top_k=top_k,
        filters=filters,
        candidate_expansion=candidate_expansion,
    )


def handle_add_book(payload: dict) -> dict:
    if not readiness_state["ready"]:
        raise RuntimeError(
            f"FAISS index modification refused: service not ready ({readiness_state['status_code']})"
        )

    book = payload.get("book", {})
    book_id = str(book.get("_id") or book.get("id", ""))
    if not book_id:
        raise ValueError("Book must include a valid '_id' or 'id'.")

    # Format text and encode
    text = embedding_adapter.format_book_text(book)
    vector = embedding_adapter.encode_query(text, normalize=(index_manager.metric == "IP"))

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
    if index_meta is not None:
        index_meta.set(
            generation_id=id_mapping.generation_id or index_meta.generation_id or IndexMetadata.create_generation_id(),
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
    if not readiness_state["ready"]:
        raise RuntimeError(
            f"FAISS index modification refused: service not ready ({readiness_state['status_code']})"
        )

    book_id = str(payload.get("book_id") or payload.get("id", ""))
    if not book_id:
        raise ValueError("Must provide book_id to delete.")

    fid = id_mapping.remove_by_mongo_id(book_id)
    if fid is not None:
        index_manager.remove_ids([fid])
        index_manager.save()
        id_mapping.save()
        index_meta.set(
            generation_id=id_mapping.generation_id or index_meta.generation_id or IndexMetadata.create_generation_id(),
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

    stats = build_index_from_books(
        books=books,
        index_type=payload.get("index_type", INDEX_TYPE),
        metric=payload.get("metric", DISTANCE_METRIC),
        model_name=payload.get("model", SBERT_MODEL_NAME),
        allow_empty=payload.get("allow_empty", False),
    )

    # Re-verify and reload active artifacts
    check_and_load_artifacts()

    return {
        "success": True,
        "stats": stats,
        "readiness": readiness_state,
    }


def handle_status() -> dict:
    file_size = INDEX_PATH.stat().st_size if INDEX_PATH.exists() else 0
    vec_count = index_manager.count if index_manager.is_initialized else 0
    map_count = len(id_mapping) if id_mapping is not None else 0

    generation_info = {
        "generation_id": index_meta.generation_id,
        "mapping_generation_id": id_mapping.generation_id,
        "generations_match": (
            bool(index_meta.generation_id and id_mapping.generation_id)
            and index_meta.generation_id == id_mapping.generation_id
        ),
    }

    return {
        "ready": readiness_state["ready"],
        "status_code": readiness_state["status_code"],
        "initialized": index_manager.is_initialized,
        "vectors_indexed": vec_count,
        "mapping_count": map_count,
        "counts_match": (vec_count == map_count),
        "dimension": index_manager.dimension,
        "metric": index_manager.metric,
        "index_type": index_manager.index_type,
        "index_file_size_bytes": file_size,
        "model_name": embedding_adapter.model_name,
        "generation": generation_info,
        "health_issues": readiness_state["errors"],
        "healthy": readiness_state["ready"],
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
        elif action in ("status", "info"):
            data = handle_status()
        elif action in ("ping", "health"):
            data = {
                "status": "healthy" if readiness_state["ready"] else "unhealthy",
                "ready": readiness_state["ready"],
                "status_code": readiness_state["status_code"],
                "count": index_manager.count if index_manager.is_initialized else 0
            }
        else:
            return json.dumps({
                "id": req_id,
                "ok": False,
                "error_code": "UNKNOWN_ACTION",
                "error": f"Unknown action: '{action}'"
            })

        return json.dumps({"id": req_id, "ok": True, "data": data}, ensure_ascii=False)
    except Exception as exc:
        sys.stderr.write(f"Error handling action '{action}': {traceback.format_exc()}\n")
        sys.stderr.flush()
        err_code = "SERVICE_NOT_READY" if not readiness_state["ready"] else "ERROR"
        return json.dumps({
            "id": req_id,
            "ok": False,
            "error_code": err_code,
            "error": str(exc),
        })


def main():
    # Signal ready
    sys.stderr.write("FAISS_BRIDGE_READY\n")
    sys.stderr.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        response = process_message(line)
        print(response, flush=True)


if __name__ == "__main__":
    main()
