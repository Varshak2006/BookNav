import json
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
LACS_ROOT = BASE_DIR / "lacs_engine"
LIBRARY_CSV = Path(
    sys.argv[1] if len(sys.argv) > 1 else BASE_DIR / "lacs_data" / "library_books.csv"
)
HISTORY_PATH = Path(
    sys.argv[2] if len(sys.argv) > 2 else BASE_DIR / "lacs_data" / "correction_history.csv"
)

sys.path.insert(0, str(LACS_ROOT))

from lacs import LACSAlgorithm  # noqa: E402


engine = LACSAlgorithm(LIBRARY_CSV, HISTORY_PATH)


def choose_suggestion(result):
    corrected = (result.get("corrected_query") or "").strip()
    original = (result.get("original_query") or "").strip().lower()

    for suggestion in result.get("suggestions", []):
        clean = str(suggestion).strip()
        if clean and clean.lower() != original:
            return clean

    if corrected and corrected.lower() != original:
        return corrected

    return None


def correct_query(query):
    result = engine.correct(query)
    confidence_level = result.get("confidence_level")
    corrected_query = result.get("corrected_query")
    normalized_original = (query or "").strip().lower()
    correction_applied = (
        confidence_level == "high"
        and bool(corrected_query)
        and corrected_query.lower() != normalized_original
    )

    suggestion = None
    if not correction_applied and confidence_level in {"medium", "high"}:
        suggestion = choose_suggestion(result)

    return {
        "query": query,
        "correctedQuery": corrected_query if correction_applied else None,
        "correctionApplied": correction_applied,
        "suggestion": suggestion,
        "confidence": result.get("confidence"),
        "confidenceLevel": confidence_level,
    }


def handle_request(payload):
    action = payload.get("action")
    if action in ("sync", "sync_books"):
        books = payload.get("books", [])
        count = engine.sync_books(books)
        return {"synced": True, "vocabulary_size": count}

    if action == "add_book":
        book = payload.get("book", {})
        new_words = engine.add_book(book)
        return {
            "added": True,
            "new_words_count": new_words,
            "vocabulary_size": len(engine.vocabulary.vocabulary),
        }

    if action == "update_book":
        old_book = payload.get("old_book", {})
        new_book = payload.get("new_book", {})
        engine.update_book(old_book, new_book)
        return {
            "updated": True,
            "vocabulary_size": len(engine.vocabulary.vocabulary),
        }

    if action == "delete_book":
        book = payload.get("book", {})
        removed = engine.delete_book(book)
        return {
            "deleted": True,
            "removed_words_count": removed,
            "vocabulary_size": len(engine.vocabulary.vocabulary),
        }

    if action == "accept_correction":
        wrong = str(payload.get("wrong", "")).strip()
        correct = str(payload.get("correct", "")).strip()
        if wrong and correct:
            engine.accept_correction(wrong, correct)
        return {"accepted": True, "wrong": wrong, "correct": correct}

    if action in ("ping", "health"):
        return {
            "status": "healthy",
            "vocabulary_size": len(engine.vocabulary.vocabulary),
        }

    # Default: spell correction query
    query = str(payload.get("query", ""))
    return correct_query(query)


for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    request_id = None
    try:
        payload = json.loads(line)
        request_id = payload.get("id")
        response = {
            "id": request_id,
            "ok": True,
            "data": handle_request(payload),
        }
    except Exception as exc:
        response = {
            "id": request_id,
            "ok": False,
            "error": str(exc),
        }

    print(json.dumps(response), flush=True)
