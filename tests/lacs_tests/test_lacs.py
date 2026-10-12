from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lacs import LACSAlgorithm, CandidateScore
from lacs.character_similarity import CharacterSimilarity
from lacs.phonetic_similarity import PhoneticSimilarity
from lacs.candidate_generator import CandidateGenerator

BASE = Path(__file__).resolve().parents[1]
engine = LACSAlgorithm(
    BASE / "data" / "library_books.csv",
    BASE / "data" / "correction_history.csv"
)
char = CharacterSimilarity()
phonetic = PhoneticSimilarity()

# ==============================================================================
# EXISTING TESTS (Preserved for backwards compatibility)
# ==============================================================================

def test_tagore():
    r = engine.correct("ravindranath tagor")
    assert "tagore" in r["corrected_query"] and "rabindranath" in r["corrected_query"]

def test_harry_potter():
    r = engine.correct("harry pottr")
    assert "potter" in r["corrected_query"]

def test_machine_learning():
    r = engine.correct("machne larning")
    assert "machine" in r["corrected_query"]
    assert "learning" in r["corrected_query"]

def test_valid_term_not_overcorrected():
    r = engine.correct("python")
    assert r["corrected_query"] == "python"

def test_levenshtein_required_cases():
    assert char.distance("machine", "machine") == 0
    assert char.distance("machne", "machine") == 1
    assert char.distance("database", "databse") == 1
    assert char.distance("", "abc") == 3
    assert char.distance("abc", "") == 3
    assert char.distance("café", "cafe") == 1
    assert char.distance("Machine", "machine") == 0

def test_similarity_bounds_and_symmetry():
    samples = [("", ""), ("abc", ""), ("kitten", "sitting"), ("python", "pythno")]
    for a, b in samples:
        assert char.distance(a, b) == char.distance(b, a)
        assert 0.0 <= char.score(a, b) <= 1.0

def test_custom_phonetic_edge_cases():
    assert phonetic.score("", "") == 1.0
    assert phonetic.score("", "abc") == 0.0
    assert phonetic.score("tagor", "tagore") > phonetic.score("tagor", "python")
    assert phonetic.key("book") == phonetic.key("boook")
    assert isinstance(phonetic.key("café"), str)

def test_candidate_generation_is_unique_and_indexed():
    candidates = engine.generator.generate("machne", limit=20)
    assert "machine" in candidates
    assert len(candidates) == len(set(candidates))
    assert len(candidates) <= 20

def test_repeated_misspelled_words_are_position_based():
    r = engine.correct("machne machne")
    assert r["corrected_query"] == "machine machine"
    changed = [c for c in r["token_corrections"] if c["auto_corrected"]]
    assert [c["token_index"] for c in changed] == [0, 1]

def test_punctuation_and_spacing_are_preserved_where_practical():
    r = engine.correct("machne,   larning!")
    assert r["corrected_query"] == "machine, learning!"

def test_numbers_isbn_and_alphanumeric_are_not_corrected():
    assert engine.correct("978-0131103627")["corrected_query"] == "978-0131103627"
    assert engine.correct("tcp ip 101")["corrected_query"] == "tcp ip 101"
    assert engine.correct("CS50")["corrected_query"] == "cs50"

def test_empty_whitespace_and_long_input_are_safe():
    assert engine.correct("")["corrected_query"] == ""
    assert engine.correct("   ")["corrected_query"] == ""
    long = "machne " * 100
    out = engine.correct(long)
    assert out["truncated"] is True
    assert isinstance(out["corrected_query"], str)

def test_transposition_and_substitution_errors():
    assert "python" in engine.correct("pyhton")["corrected_query"]
    assert "database" in engine.correct("databaze")["corrected_query"]

def test_no_candidate_case_is_deterministic():
    first = engine.correct("zzzzzzzz")
    second = engine.correct("zzzzzzzz")
    assert first["corrected_query"] == second["corrected_query"]
    assert first["suggestions"] == second["suggestions"]

def test_confidence_margin_blocks_ambiguous_autocorrect():
    r = engine.correct("ai")
    assert r["corrected_query"] == "ai"

def test_history_requires_minimum_frequency(tmp_path):
    local = LACSAlgorithm(BASE / "data" / "library_books.csv", tmp_path / "history.csv")
    local.accept_correction("machne", "machine")
    assert local.history.score("machne", "machine") == 0.0
    local.accept_correction("machne", "machine")
    assert local.history.score("machne", "machine") == 1.0

def test_final_scores_are_finite_and_top_k_limited():
    r = engine.correct("machne")
    details = r["token_details"]["machne"]
    assert len(details) <= engine.config.top_k
    for item in details:
        assert 0.0 <= item["score"] <= 1.0

# ==============================================================================
# PHASE 18 COMPREHENSIVE CATEGORIES (A through Z)
# ==============================================================================

def test_category_a_exact_words():
    """Category A: exact vocabulary words should never be modified."""
    exact_queries = ["machine learning", "python programming", "database system", "artificial intelligence"]
    for q in exact_queries:
        res = engine.correct(q)
        assert res["corrected_query"] == q
        assert res["corrections"] == {}

def test_category_b_insertion_errors():
    """Category B: insertion typo (extra letter)."""
    assert "machine" in engine.correct("machnine")["corrected_query"]
    assert "python" in engine.correct("pythoon")["corrected_query"]

def test_category_c_deletion_errors():
    """Category C: deletion typo (missing letter)."""
    assert "machine" in engine.correct("machne")["corrected_query"]
    assert "database" in engine.correct("databse")["corrected_query"]

def test_category_d_substitution_errors():
    """Category D: substitution typo (wrong letter)."""
    assert "database" in engine.correct("databaze")["corrected_query"]
    assert "network" in engine.correct("netwurk")["corrected_query"] or "networking" in engine.correct("netwurking")["corrected_query"]

def test_category_e_transposition_errors():
    """Category E: transposition typo (swapped adjacent letters)."""
    assert "python" in engine.correct("pyhton")["corrected_query"]
    assert "learning" in engine.correct("leanring")["corrected_query"]

def test_category_f_author_name_errors():
    """Category F: author names correction."""
    res = engine.correct("ravindranath tagor")
    assert "rabindranath" in res["corrected_query"]
    assert "tagore" in res["corrected_query"]

def test_category_g_book_title_errors():
    """Category G: book titles correction."""
    res = engine.correct("harry pottr philospher")
    assert "potter" in res["corrected_query"]
    assert "philosopher" in res["corrected_query"]

def test_category_h_category_errors():
    """Category H: library category names correction."""
    assert "networking" in engine.correct("netwroking")["corrected_query"]
    assert "poetry" in engine.correct("poety")["corrected_query"]
    assert "fantasy" in engine.correct("fantacy")["corrected_query"]

def test_category_i_multiple_misspellings():
    """Category I: multiple misspellings in a single query."""
    res = engine.correct("machne larning algoritms")
    assert res["corrected_query"] == "machine learning algorithms"

def test_category_j_context_ambiguity():
    """Category J: context guides ambiguous token to correct library term."""
    # "deep" + "larning" should strongly favor "learning" due to bigram "deep learning"
    res = engine.correct("deep larning")
    assert res["corrected_query"] == "deep learning"

def test_category_k_valid_rare_words():
    """Category K: valid but infrequent words are preserved."""
    assert engine.correct("gitanjali")["corrected_query"] == "gitanjali"
    assert engine.correct("tanenbaum")["corrected_query"] == "tanenbaum"

def test_category_l_empty_input():
    """Category L: empty string input."""
    res = engine.correct("")
    assert res["corrected_query"] == ""
    assert res["confidence"] == 0.0

def test_category_m_whitespace_input():
    """Category M: whitespace-only input."""
    res = engine.correct("   \t  \n  ")
    assert res["corrected_query"] == ""
    assert res["confidence"] == 0.0

def test_category_n_long_input():
    """Category N: oversized query safe handling."""
    long_q = "python " * 200
    res = engine.correct(long_q)
    assert res["truncated"] is True
    assert len(res["corrected_query"]) <= engine.config.max_query_length + 50

def test_category_o_punctuation():
    """Category O: query with punctuation preserved."""
    res = engine.correct("machne, larning; databse!")
    assert res["corrected_query"] == "machine, learning; database!"

def test_category_p_numbers():
    """Category P: numbers are not mangled."""
    res = engine.correct("cs 101 python 3")
    assert "101" in res["corrected_query"]
    assert "3" in res["corrected_query"]

def test_category_q_isbn():
    """Category Q: ISBN formats are skipped safely."""
    res = engine.correct("isbn 978-0131103627")
    assert "978-0131103627" in res["corrected_query"]

def test_category_r_unicode():
    """Category R: Unicode characters normalized and handled."""
    assert engine.correct("café")["corrected_query"] == "cafe" or "café" in engine.correct("café")["corrected_query"]
    assert char.distance("café", "cafe") == 1

def test_category_s_repeated_words():
    """Category S: repeated valid words."""
    res = engine.correct("python python")
    assert res["corrected_query"] == "python python"

def test_category_t_repeated_misspelled_words():
    """Category T: repeated misspelled words handled independently by position."""
    res1 = engine.correct("machne machne")
    assert res1["corrected_query"] == "machine machine"

    res2 = engine.correct("python machne machne")
    assert res2["corrected_query"] == "python machine machine"

def test_category_u_mixed_case():
    """Category U: mixed case normalized gracefully."""
    res = engine.correct("MachNe LaRnInG")
    assert res["corrected_query"] == "machine learning"

def test_category_v_no_candidate_cases():
    """Category V: unknown words with no plausible candidates."""
    res = engine.correct("xyzqwertyuiop")
    assert res["corrected_query"] == "xyzqwertyuiop"
    assert res["confidence_level"] == "low"

def test_category_w_tied_candidates():
    """Category W: tied candidates resolved deterministically."""
    # When scores are identical, tie breaking uses:
    # 1. library_score, 2. char_score, 3. context_score, 4. frequency_score, 5. candidate alphabetical
    cand_b = CandidateScore("beta", 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    cand_a = CandidateScore("alpha", 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    ranked = sorted([cand_b, cand_a], key=lambda c: (
        -c.final_score, -c.library_score, -c.character_score, -c.context_score, -c.frequency_score, c.candidate
    ))
    assert [c.candidate for c in ranked] == ["alpha", "beta"]

def test_category_x_confidence_boundary_cases():
    """Category X: boundary confidence does not trigger auto-correction."""
    res = engine.correct("ai")
    assert res["corrected_query"] == "ai"
    assert res["confidence_level"] != "high" or res["corrections"] == {}

def test_category_y_history_behavior(tmp_path):
    """Category Y: history repository records and retrieves corrections."""
    h_file = tmp_path / "hist.csv"
    algo = LACSAlgorithm(BASE / "data" / "library_books.csv", h_file)
    algo.accept_correction("databse", "database")
    assert algo.history.get_frequency("databse", "database") == 1

def test_category_z_deterministic_ranking():
    """Category Z: identical runs give identical output rankings."""
    q = "machne larning databse"
    run1 = engine.correct(q)
    run2 = engine.correct(q)
    assert run1["corrected_query"] == run2["corrected_query"]
    assert run1["suggestions"] == run2["suggestions"]
    assert run1["confidence"] == run2["confidence"]
    assert run1["token_corrections"] == run2["token_corrections"]

if __name__ == "__main__":
    import pytest
    pytest.main([__file__])
