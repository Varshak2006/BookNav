"""Phase Thirteen Automated Test Suite.

Covers all Phase Thirteen test categories:
A. SPELLING ERRORS
B. LIBRARY QUERIES
C. VALID-QUERY PRESERVATION
D. EDGE CASES
E. CONFIDENCE BEHAVIOUR
F. VOCABULARY
G. DATASET INTEGRITY
H. BOOKNAV INTEGRATION CONTRACT
"""

import csv
import io
from pathlib import Path
import pytest

from lacs import LACSAlgorithm, LACSConfig
from lacs.character_similarity import CharacterSimilarity
from lacs.phonetic_similarity import PhoneticSimilarity
from lacs.confidence import ConfidenceDecision
from lacs.vocabulary import VocabularyManager

BASE_DIR = Path(__file__).resolve().parents[1]
LIBRARY_CSV = BASE_DIR / "data" / "library_books.csv"
HISTORY_CSV = BASE_DIR / "data" / "correction_history.csv"
ENGINEERING_CSV = BASE_DIR / "datasets" / "engineering_books.csv"
VOCABULARY_CSV = BASE_DIR / "datasets" / "lacs_vocabulary.csv"


@pytest.fixture
def engine():
    return LACSAlgorithm(LIBRARY_CSV, HISTORY_CSV)


# ==============================================================================
# A. SPELLING ERRORS
# ==============================================================================

def test_a1_character_insertion(engine):
    """Extra character in token: 'databasse' -> 'database'."""
    res = engine.correct("databasse")
    assert "database" in res["corrected_query"]


def test_a2_character_deletion(engine):
    """Missing character in token: 'pythn' -> 'python'."""
    res = engine.correct("pythn")
    assert "python" in res["corrected_query"]


def test_a3_character_substitution(engine):
    """Substituted character: 'databaze' -> 'database'."""
    res = engine.correct("databaze")
    assert "database" in res["corrected_query"]


def test_a4_adjacent_transposition(engine):
    """Swapped adjacent characters: 'pyhton' -> 'python'."""
    res = engine.correct("pyhton")
    assert "python" in res["corrected_query"]


def test_a5_multiple_misspelled_words(engine):
    """Multiple typos in same query: 'machne larning' -> 'machine learning'."""
    res = engine.correct("machne larning")
    assert res["corrected_query"] == "machine learning"
    assert res["confidence_level"] == "high"


# ==============================================================================
# B. LIBRARY QUERIES
# ==============================================================================

def test_b1_misspelled_book_title(engine):
    """'clean coed' -> 'clean code'."""
    res = engine.correct("clean coed")
    assert "clean code" in res["corrected_query"]


def test_b2_misspelled_author_name(engine):
    """'ravindranath tagor' -> 'rabindranath tagore'."""
    res = engine.correct("ravindranath tagor")
    assert "rabindranath" in res["corrected_query"]
    assert "tagore" in res["corrected_query"]


def test_b3_misspelled_subject_category(engine):
    """'fantazy' -> 'fantasy'."""
    res = engine.correct("fantazy")
    assert "fantasy" in res["corrected_query"]


def test_b4_technical_terminology(engine):
    """'netwroks' -> 'networks'."""
    res = engine.correct("netwroks")
    assert "networks" in res["corrected_query"]


def test_b5_multi_term_contextual_query(engine):
    """'database systm concepts' -> 'database system concepts'."""
    res = engine.correct("database systm concepts")
    assert res["corrected_query"] == "database system concepts"


# ==============================================================================
# C. VALID-QUERY PRESERVATION
# ==============================================================================

def test_c1_correctly_spelled_query_preserved(engine):
    """Valid queries must never be changed."""
    res = engine.correct("machine learning")
    assert res["corrected_query"] == "machine learning"
    assert res["corrections"] == {}
    assert res["confidence"] == 1.0


def test_c2_valid_rare_author_preserved(engine):
    """Valid rare author name remains untouched."""
    res = engine.correct("sedgewick")
    assert res["corrected_query"] == "sedgewick"
    assert res["corrections"] == {}


def test_c3_valid_rare_title_preserved(engine):
    """Valid rare title preserved."""
    res = engine.correct("gitanjali")
    assert res["corrected_query"] == "gitanjali"
    assert res["corrections"] == {}


def test_c4_apostrophe_phrase_preserved(engine):
    """'philosopher's' with apostrophe is not corrupted."""
    res = engine.correct("harry potter and the philosopher's stone")
    assert "philosopher's" in res["corrected_query"]
    assert res["corrections"] == {}


# ==============================================================================
# D. EDGE CASES
# ==============================================================================

def test_d1_empty_input(engine):
    res = engine.correct("")
    assert res["corrected_query"] == ""
    assert res["confidence_level"] == "low"


def test_d2_whitespace_only(engine):
    res = engine.correct("    \t  \n  ")
    assert res["corrected_query"] == ""
    assert res["confidence_level"] == "low"


def test_d3_isbn_and_numbers(engine):
    """ISBN numbers are passed through safely without error or mutation."""
    res = engine.correct("isbn 978-0131103627")
    assert "978-0131103627" in res["corrected_query"]


def test_d4_mixed_capitalization(engine):
    res = engine.correct("MaChInE LeArNiNg")
    assert res["corrected_query"] == "machine learning"


def test_d5_repeated_misspelled_words(engine):
    """Repeated misspellings handled at distinct token indices."""
    res = engine.correct("machne machne")
    assert res["corrected_query"] == "machine machine"
    indices = [c["token_index"] for c in res["token_corrections"] if c["auto_corrected"]]
    assert indices == [0, 1]


def test_d6_unknown_term(engine):
    """Nonsense string has no valid correction and falls back safely."""
    res = engine.correct("zyxwvuabcdefgh")
    assert res["corrected_query"] == "zyxwvuabcdefgh"
    assert res["confidence_level"] == "low"


# ==============================================================================
# E. CONFIDENCE BEHAVIOUR
# ==============================================================================

def test_e1_high_confidence_auto_correct():
    decision = ConfidenceDecision(auto_threshold=0.47, medium_threshold=0.45, minimum_margin=0.03)
    dec = decision.decide([("candidate", 0.65), ("alt", 0.45)])
    assert dec["level"] == "high"
    assert dec["auto_correct"] is True
    assert dec["score_margin"] == 0.20


def test_e2_medium_confidence_suggestion():
    decision = ConfidenceDecision(auto_threshold=0.47, medium_threshold=0.45, minimum_margin=0.03)
    dec = decision.decide([("candidate", 0.46), ("alt", 0.40)])
    assert dec["level"] == "medium"
    assert dec["auto_correct"] is False


def test_e3_low_confidence_fallback():
    decision = ConfidenceDecision(auto_threshold=0.47, medium_threshold=0.45, minimum_margin=0.03)
    dec = decision.decide([("candidate", 0.30)])
    assert dec["level"] == "low"
    assert dec["auto_correct"] is False


def test_e4_margin_gating_similar_scores():
    """Tied or near-tied scores prevent auto-correction even if score is high."""
    decision = ConfidenceDecision(auto_threshold=0.47, medium_threshold=0.45, minimum_margin=0.03)
    dec = decision.decide([("cand1", 0.60), ("cand2", 0.59)])
    assert dec["score_margin"] == 0.01
    assert dec["level"] == "medium"
    assert dec["auto_correct"] is False


# ==============================================================================
# F. VOCABULARY MANAGEMENT
# ==============================================================================

def test_f1_empty_vocabulary_handling(tmp_path):
    empty_csv = tmp_path / "empty.csv"
    empty_csv.write_text("title,author,category,keywords,description\n", encoding="utf-8")
    vm = VocabularyManager(empty_csv)
    assert len(vm.vocabulary) == 0
    assert vm.contains("data")  # General dictionary fallback works


def test_f2_dynamic_add_and_remove(tmp_path):
    csv_file = tmp_path / "lib.csv"
    csv_file.write_text("title,author,category,keywords,description\n", encoding="utf-8")
    engine = LACSAlgorithm(csv_file)
    assert not engine.vocabulary.contains("compiler")

    engine.add_book({
        "title": "Modern Compiler Implementation",
        "author": "Andrew Appel",
        "category": "Computer Science",
    })
    assert engine.vocabulary.contains("compiler")
    assert engine.vocabulary.contains("appel")

    # Correct misspelled word
    res = engine.correct("compeiler")
    assert "compiler" in res["corrected_query"]

    # Delete book
    engine.delete_book({
        "title": "Modern Compiler Implementation",
        "author": "Andrew Appel",
        "category": "Computer Science",
    })
    assert not engine.vocabulary.contains("appel")


def test_f3_sync_books_bulk(tmp_path):
    csv_file = tmp_path / "lib.csv"
    csv_file.write_text("title,author,category,keywords,description\n", encoding="utf-8")
    engine = LACSAlgorithm(csv_file)

    books = [
        {"title": "Distributed Algorithms", "author": "Nancy Lynch", "category": "Computer Science"},
        {"title": "Computer Networks", "author": "Andrew Tanenbaum", "category": "Networking"},
    ]
    engine.sync_books(books)
    assert engine.vocabulary.contains("lynch")
    assert engine.vocabulary.contains("tanenbaum")
    assert engine.vocabulary.contains("distributed")


def test_f4_load_lacs_vocabulary_csv():
    """VocabularyManager can load directly from datasets/lacs_vocabulary.csv."""
    assert VOCABULARY_CSV.exists()
    vm = VocabularyManager(VOCABULARY_CSV)
    assert vm.contains("computer")
    assert vm.contains("engineering")
    assert vm.contains("algorithms")


# ==============================================================================
# G. DATASET INTEGRITY
# ==============================================================================

def test_g1_engineering_dataset_columns():
    """Verify required columns in engineering_books.csv."""
    assert ENGINEERING_CSV.exists(), "engineering_books.csv must exist"
    required = {
        "openlibrary_work_id", "openlibrary_edition_id", "title",
        "authors", "subjects", "isbn", "publication_year", "language", "source"
    }
    with ENGINEERING_CSV.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert required.issubset(set(reader.fieldnames))


def test_g2_engineering_dataset_non_empty_and_valid():
    """Verify records have non-empty titles and valid Open Library work keys."""
    with ENGINEERING_CSV.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) >= 1000, f"Expected at least 1,000 engineering books, got {len(rows)}"
    for r in rows[:100]:
        assert r["title"].strip() != ""
        assert r["openlibrary_work_id"].strip().startswith("OL")
        assert r["source"] == "openlibrary"


def test_g3_engineering_dataset_reload_and_parse():
    """CSV can be reopened and parsed without encoding errors."""
    with ENGINEERING_CSV.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        row_count = sum(1 for _ in reader)
    assert row_count >= 1000


# ==============================================================================
# H. BOOKNAV INTEGRATION CONTRACT
# ==============================================================================

def test_h1_sync_books_contract(engine):
    """sync_books returns count of terms."""
    count = engine.sync_books([
        {"title": "Operating Systems", "author": "Silberschatz", "category": "CS"}
    ])
    assert isinstance(count, int)
    assert count > 0


def test_h2_accept_correction_persists(tmp_path):
    """User feedback is recorded in history."""
    hist_file = tmp_path / "hist.csv"
    engine = LACSAlgorithm(LIBRARY_CSV, hist_file)
    engine.accept_correction("pythn", "python")
    assert engine.history.get_frequency("pythn", "python") == 1
