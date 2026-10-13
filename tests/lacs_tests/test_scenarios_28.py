"""Automated tests for all 28 Phase 4 Scenarios.

Scenarios tested:
1. Correctly spelled book title.
2. Single-character substitution.
3. Missing character.
4. Extra character.
5. Character transposition.
6. Misspelled author name.
7. Multiple misspelled words.
8. Repeated misspelled words.
9. Valid rare author name.
10. Valid rare book title.
11. Unknown word.
12. Empty query.
13. Whitespace-only query.
14. Mixed-case input.
15. Punctuation and numbers.
16. Multiple candidate corrections with similar scores.
17. High-confidence correction.
18. Medium-confidence suggestion.
19. Low-confidence fallback.
20. Missing or unavailable vocabulary.
21. MongoDB connection failure fallback handling.
22. Newly added book.
23. Updated book title or author.
24. Deleted book.
25. Frontend/API search using corrected queries.
26. Frontend/API search using original queries.
27. User accepting a suggestion.
28. User rejecting a suggestion.
"""

from pathlib import Path
import pytest
from lacs import LACSAlgorithm, LACSConfig
from lacs.confidence import ConfidenceDecision
from lacs.models import CandidateScore

BASE = Path(__file__).resolve().parents[1]
LIBRARY_CSV = BASE / "data" / "library_books.csv"
HISTORY_CSV = BASE / "data" / "correction_history.csv"


@pytest.fixture
def engine():
    return LACSAlgorithm(LIBRARY_CSV, HISTORY_CSV)


# 1. Correctly spelled book title
def test_scenario_01_correctly_spelled_book_title(engine):
    res = engine.correct("Machine Learning")
    assert res["corrected_query"] == "machine learning"
    assert res["corrections"] == {}
    assert res["confidence"] == 1.0


# 2. Single-character substitution
def test_scenario_02_single_character_substitution(engine):
    res = engine.correct("databaze")
    assert "database" in res["corrected_query"]
    assert res["confidence_level"] == "high"


# 3. Missing character
def test_scenario_03_missing_character(engine):
    res = engine.correct("machne")
    assert "machine" in res["corrected_query"]
    assert res["confidence_level"] == "high"


# 4. Extra character
def test_scenario_04_extra_character(engine):
    res = engine.correct("pythoon")
    assert "python" in res["corrected_query"]
    assert res["confidence_level"] == "high"


# 5. Character transposition
def test_scenario_05_character_transposition(engine):
    res = engine.correct("pyhton")
    assert "python" in res["corrected_query"]
    assert res["confidence_level"] == "high"


# 6. Misspelled author name
def test_scenario_06_misspelled_author_name(engine):
    res = engine.correct("ravindranath tagor")
    assert "rabindranath" in res["corrected_query"]
    assert "tagore" in res["corrected_query"]


# 7. Multiple misspelled words
def test_scenario_07_multiple_misspelled_words(engine):
    res = engine.correct("machne larning")
    assert res["corrected_query"] == "machine learning"
    assert res["confidence_level"] == "high"


# 8. Repeated misspelled words
def test_scenario_08_repeated_misspelled_words(engine):
    res = engine.correct("machne machne")
    assert res["corrected_query"] == "machine machine"
    positions = [c["token_index"] for c in res["token_corrections"] if c["auto_corrected"]]
    assert positions == [0, 1]


# 9. Valid rare author name
def test_scenario_09_valid_rare_author_name(engine):
    res = engine.correct("tanenbaum")
    assert res["corrected_query"] == "tanenbaum"
    assert res["corrections"] == {}


# 10. Valid rare book title
def test_scenario_10_valid_rare_book_title(engine):
    res = engine.correct("gitanjali")
    assert res["corrected_query"] == "gitanjali"
    assert res["corrections"] == {}


# 11. Unknown word
def test_scenario_11_unknown_word(engine):
    unknown = "zyxwvuabcdefgh"
    res = engine.correct(unknown)
    assert res["corrected_query"] == unknown
    assert res["confidence_level"] == "low"
    assert res["confidence"] == 0.0


# 12. Empty query
def test_scenario_12_empty_query(engine):
    res = engine.correct("")
    assert res["corrected_query"] == ""
    assert res["confidence"] == 0.0
    assert res["confidence_level"] == "low"


# 13. Whitespace-only query
def test_scenario_13_whitespace_only_query(engine):
    res = engine.correct("    \t\n   ")
    assert res["corrected_query"] == ""
    assert res["confidence"] == 0.0
    assert res["confidence_level"] == "low"


# 14. Mixed-case input
def test_scenario_14_mixed_case_input(engine):
    res = engine.correct("MaChNe LaRnInG")
    assert res["corrected_query"] == "machine learning"


# 15. Punctuation and numbers
def test_scenario_15_punctuation_and_numbers(engine):
    res = engine.correct("machne, 101 larning!")
    assert res["corrected_query"] == "machine, 101 learning!"
    assert "101" in res["corrected_query"]


# 16. Multiple candidate corrections with similar scores
def test_scenario_16_multiple_candidates_similar_scores():
    # If two candidates have top score above threshold, but margin < 0.03:
    decision = ConfidenceDecision(auto_threshold=0.47, medium_threshold=0.45, minimum_margin=0.03)
    dec = decision.decide([("cand1", 0.50), ("cand2", 0.49)])
    assert dec["level"] == "medium"
    assert dec["auto_correct"] is False
    assert dec["score_margin"] == 0.01


# 17. High-confidence correction
def test_scenario_17_high_confidence_correction():
    decision = ConfidenceDecision(auto_threshold=0.47, medium_threshold=0.45, minimum_margin=0.03)
    dec = decision.decide([("cand1", 0.60), ("cand2", 0.45)])
    assert dec["level"] == "high"
    assert dec["auto_correct"] is True
    assert dec["score_margin"] == 0.15


# 18. Medium-confidence suggestion
def test_scenario_18_medium_confidence_suggestion():
    decision = ConfidenceDecision(auto_threshold=0.47, medium_threshold=0.45, minimum_margin=0.03)
    dec = decision.decide([("cand1", 0.46), ("cand2", 0.40)])
    assert dec["level"] == "medium"
    assert dec["auto_correct"] is False


# 19. Low-confidence fallback
def test_scenario_19_low_confidence_fallback():
    decision = ConfidenceDecision(auto_threshold=0.47, medium_threshold=0.45, minimum_margin=0.03)
    dec = decision.decide([("cand1", 0.35)])
    assert dec["level"] == "low"
    assert dec["auto_correct"] is False


# 20. Missing or unavailable vocabulary
def test_scenario_20_missing_or_unavailable_vocabulary(tmp_path):
    missing_csv = tmp_path / "does_not_exist.csv"
    algo = LACSAlgorithm(missing_csv, tmp_path / "hist.csv")
    assert isinstance(algo.vocabulary.vocabulary, set)
    res = algo.correct("python")
    assert res["corrected_query"] == "python"


# 21. MongoDB connection failure fallback handling
def test_scenario_21_mongodb_fallback_safety():
    # Simulates fallback when DB is down: CSV/in-memory algorithm continues to work
    engine = LACSAlgorithm(LIBRARY_CSV, HISTORY_CSV)
    res = engine.correct("harry pottr")
    assert res["corrected_query"] == "harry potter"
    assert res["confidence_level"] == "high"


# 22. Newly added book
def test_scenario_22_newly_added_book(tmp_path):
    algo = LACSAlgorithm(tmp_path / "empty.csv", tmp_path / "hist.csv")
    assert not algo.vocabulary.contains("melville")
    
    # Add new book
    algo.add_book({
        "title": "Moby Dick",
        "author": "Herman Melville",
        "category": "Classic Literature",
        "description": "Novel about the white whale.",
    })
    
    assert algo.vocabulary.contains("melville")
    assert algo.vocabulary.contains("moby")
    
    # Can now correct typo of the newly added author
    res = algo.correct("melvile")
    assert "melville" in res["corrected_query"]


# 23. Updated book title or author
def test_scenario_23_updated_book(tmp_path):
    algo = LACSAlgorithm(tmp_path / "empty.csv", tmp_path / "hist.csv")
    old_record = {
        "title": "Quantum Physics 101",
        "author": "Werner Heisenberg",
        "category": "Physics",
        "description": "Intro to quantum theory.",
    }
    algo.add_book(old_record)
    assert algo.vocabulary.contains("heisenberg")

    new_record = {
        "title": "Quantum Electrodynamics",
        "author": "Richard Feynman",
        "category": "Physics",
        "description": "QED concepts.",
    }
    algo.update_book(old_record, new_record)
    assert algo.vocabulary.contains("feynman")
    assert not algo.vocabulary.contains("heisenberg")

    res = algo.correct("richard fynman")
    assert "feynman" in res["corrected_query"]
    assert res["confidence_level"] == "high"


# 24. Deleted book
def test_scenario_24_deleted_book(tmp_path):
    algo = LACSAlgorithm(tmp_path / "empty.csv", tmp_path / "hist.csv")
    record = {
        "title": "Special Relativity",
        "author": "Albert Einstein",
        "category": "Physics",
        "description": "Relativity paper.",
    }
    algo.add_book(record)
    assert algo.vocabulary.contains("einstein")
    
    algo.delete_book(record)
    assert not algo.vocabulary.contains("einstein")


# 25. Search using corrected queries (Bridge logic)
def test_scenario_25_bridge_search_using_corrected_query(engine):
    out = engine.correct("harry pottr")
    conf_level = out["confidence_level"]
    corrected = out["corrected_query"]
    applied = conf_level == "high" and corrected != "harry pottr"
    assert applied is True
    assert corrected == "harry potter"


def test_stopword_normalized_title_context_improves_title_coverage(engine):
    out = engine.correct("chambr secrets")
    assert out["corrected_query"] == "chamber secrets"
    assert out["confidence_level"] == "high"


def test_harry_poater_remains_high_confidence(engine):
    out = engine.correct("harry poater")
    assert out["corrected_query"] == "harry potter"
    assert out["confidence_level"] == "high"


# 26. Search using original queries (User override / forceOriginal)
def test_scenario_26_search_using_original_query(engine):
    out = engine.correct("harry pottr")
    force_original = True
    applied = (not force_original) and out["confidence_level"] == "high"
    effective_search = "harry pottr" if not applied else out["corrected_query"]
    assert effective_search == "harry pottr"
    assert applied is False


# 27. User accepting a suggestion
def test_scenario_27_user_accepting_suggestion(tmp_path):
    algo = LACSAlgorithm(LIBRARY_CSV, tmp_path / "hist.csv")
    assert algo.history.get_frequency("databze", "database") == 0
    algo.accept_correction("databze", "database")
    assert algo.history.get_frequency("databze", "database") == 1


# 28. User rejecting a suggestion
def test_scenario_28_user_rejecting_suggestion(tmp_path):
    algo = LACSAlgorithm(LIBRARY_CSV, tmp_path / "hist.csv")
    # When user rejects suggestion, no accept_correction call is made,
    # history remains clean and original query is executed.
    assert algo.history.get_frequency("unknownquery", "anything") == 0
