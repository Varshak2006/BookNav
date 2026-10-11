"""
FAISS Bridge - stdin/stdout IPC service for BookNav.

Works identically to lacs_bridge.py: reads JSON-line commands from
stdin, dispatches them to the FAISSSearchService, and writes JSON
responses to stdout.

Usage:
    python faiss_bridge.py
"""

import json
import logging
import sys
import traceback
from pathlib import Path

# Ensure faiss_engine is importable
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from faiss_engine.faiss_search import FAISSSearchService
from faiss_engine.embedding_adapter import get_model_info
from faiss_engine import config

# Configure logging to stderr (stdout is reserved for IPC)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [FAISS] %(levelname)s %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global service instance
# ---------------------------------------------------------------------------

service = FAISSSearchService()


def initialize():
    """Try to load an existing index from disk."""
    try:
        result = service.load()
        logger.info("Loaded existing FAISS index: %s", result)
        return True
    except FileNotFoundError:
        logger.info("No existing FAISS index found. Will need to build one.")
        return False
    except Exception as exc:
        logger.error("Failed to load FAISS index: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


def handle_search(payload):
    """Handle a search request."""
    query = str(payload.get("query", "")).strip()
    if not query:
        return {"error": "Search query is required."}

    top_k = int(payload.get("top_k", config.DEFAULT_TOP_K))
    filters = payload.get("filters") or {}

    # Validate filters: only allow known fields
    allowed_filter_fields = {
        "author", "category", "keywords", "title", "description",
        "shelf", "rack", "location",
    }
    clean_filters = {}
    for k, v in filters.items():
        if k in allowed_filter_fields and v:
            clean_filters[k] = str(v)

    return service.search(query=query, top_k=top_k, filters=clean_filters)


def handle_build(payload):
    """Build the index from provided book data."""
    books = payload.get("books", [])
    if not books:
        return {"error": "No books provided for indexing."}

    result = service.build_index(books)

    # Auto-save after build
    try:
        service.save()
        result["saved"] = True
    except Exception as exc:
        logger.error("Failed to save index after build: %s", exc)
        result["saved"] = False
        result["save_error"] = str(exc)

    return result


def handle_add_book(payload):
    """Add a single book to the index."""
    book = payload.get("book", {})
    if not book:
        return {"error": "No book data provided."}

    result = service.add_book(book)

    # Auto-save
    try:
        service.save()
        result["saved"] = True
    except Exception as exc:
        result["saved"] = False

    return result


def handle_remove_book(payload):
    """Remove a book from the index."""
    mongo_id = str(payload.get("book_id", "")).strip()
    if not mongo_id:
        return {"error": "book_id is required."}

    result = service.remove_book(mongo_id)

    try:
        service.save()
        result["saved"] = True
    except Exception:
        result["saved"] = False

    return result


def handle_rebuild(payload):
    """Full rebuild from provided book list."""
    books = payload.get("books", [])
    result = service.rebuild(books)

    try:
        service.save()
        result["saved"] = True
    except Exception as exc:
        result["saved"] = False
        result["save_error"] = str(exc)

    return result


def handle_status(_payload):
    """Return index status."""
    status = service.get_status()
    try:
        model_info = get_model_info()
        status["model_info"] = model_info
    except Exception:
        status["model_info"] = None
    return status


def handle_health(_payload):
    """Health check."""
    return {
        "status": "healthy",
        "is_ready": service.is_ready,
        "total_vectors": service.total_vectors,
    }


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

HANDLERS = {
    "search": handle_search,
    "build": handle_build,
    "add_book": handle_add_book,
    "remove_book": handle_remove_book,
    "rebuild": handle_rebuild,
    "status": handle_status,
    "health": handle_health,
}


def handle_request(payload):
    action = payload.get("action", "search")
    handler = HANDLERS.get(action)

    if handler is None:
        return {"error": f"Unknown action: {action}"}

    return handler(payload)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    logger.info("FAISS bridge starting...")
    initialize()
    logger.info("FAISS bridge ready for commands.")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        request_id = None
        try:
            payload = json.loads(line)
            request_id = payload.get("id")
            data = handle_request(payload)
            response = {"id": request_id, "ok": True, "data": data}
        except Exception as exc:
            logger.error("Error handling request: %s\n%s", exc, traceback.format_exc())
            response = {"id": request_id, "ok": False, "error": str(exc)}

        print(json.dumps(response, default=str), flush=True)


if __name__ == "__main__":
    main()
