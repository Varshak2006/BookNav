"""Property and Invariant tests for LACS (Phase 19).

Verifies fundamental mathematical and algorithmic invariants:
1. distance(a, a) == 0
2. distance(a, b) == distance(b, a) (symmetry)
3. distance(a, "") == len(a)
4. similarity score is within [0, 1]
5. candidate scores are finite
6. confidence is within [0, 1]
7. candidate lists contain no duplicates
8. top_k never returns more than K candidates
9. token count preservation across normalization spans
10. deterministic input produces identical deterministic output
11. valid vocabulary words are never modified unnecessarily
12. empty / whitespace input never crashes
"""

import math
from pathlib import Path
from lacs import LACSAlgorithm, LACSConfig
from lacs.character_similarity import CharacterSimilarity
from lacs.phonetic_similarity import PhoneticSimilarity

BASE = Path(__file__).resolve().parents[1]
char_sim = CharacterSimilarity()
phonetic_sim = PhoneticSimilarity()
engine = LACSAlgorithm(
    BASE / "data" / "library_books.csv",
    BASE / "data" / "correction_history.csv"
)


def test_invariant_1_identity_distance():
    """Invariant 1: distance(a, a) == 0."""
    words = ["", "a", "algorithm", "rabindranath", "tagore", "machine", "café", "12345"]
    for w in words:
        assert char_sim.distance(w, w) == 0, f"Identity failed for '{w}'"


def test_invariant_2_symmetry():
    """Invariant 2: distance(a, b) == distance(b, a)."""
    pairs = [
        ("machine", "machne"),
        ("database", "databse"),
        ("python", "pyhton"),
        ("rabindranath", "ravindranath"),
        ("", "abc"),
        ("kitten", "sitting"),
        ("short", "muchlongerword"),
        ("café", "cafe"),
    ]
    for a, b in pairs:
        assert char_sim.distance(a, b) == char_sim.distance(b, a), f"Symmetry failed for '{a}', '{b}'"


def test_invariant_3_empty_string_distance():
    """Invariant 3: distance(a, '') == len(a)."""
    samples = ["", "x", "test", "algorithms", "supercalifragilistic"]
    for s in samples:
        assert char_sim.distance(s, "") == len(s)
        assert char_sim.distance("", s) == len(s)


def test_invariant_4_similarity_bounds():
    """Invariant 4: similarity is within [0.0, 1.0] and never NaN."""
    pairs = [
        ("", ""),
        ("a", ""),
        ("", "b"),
        ("identical", "identical"),
        ("totally", "different"),
        ("sub", "substitute"),
        ("café", "cafe"),
    ]
    for a, b in pairs:
        score = char_sim.score(a, b)
        assert not math.isnan(score), f"Score is NaN for '{a}', '{b}'"
        assert not math.isinf(score), f"Score is Inf for '{a}', '{b}'"
        assert 0.0 <= score <= 1.0, f"Score out of bounds [{score}] for '{a}', '{b}'"

        pscore = phonetic_sim.score(a, b)
        assert not math.isnan(pscore), f"Phonetic score is NaN for '{a}', '{b}'"
        assert 0.0 <= pscore <= 1.0, f"Phonetic score out of bounds [{pscore}] for '{a}', '{b}'"


def test_invariant_5_candidate_scores_are_finite():
    """Invariant 5: all computed component and final candidate scores are finite and within [0, 1]."""
    res = engine.correct("machne larning algoritms")
    for tc in res["token_corrections"]:
        for c in tc["candidates"]:
            score = c["score"]
            assert math.isfinite(score)
            assert 0.0 <= score <= 1.0
            for feat_name, feat_val in c["features"].items():
                assert math.isfinite(feat_val), f"Feature {feat_name} not finite"
                assert 0.0 <= feat_val <= 1.0, f"Feature {feat_name} out of bounds"


def test_invariant_6_confidence_bounds():
    """Invariant 6: confidence is within [0.0, 1.0]."""
    queries = [
        "",
        "   ",
        "python",
        "machne",
        "machne larning",
        "xyzqwrtslkj",
        "ravindranath tagor poetry",
    ]
    for q in queries:
        res = engine.correct(q)
        conf = res["confidence"]
        assert math.isfinite(conf)
        assert 0.0 <= conf <= 1.0, f"Confidence {conf} out of bounds for '{q}'"


def test_invariant_7_no_duplicate_candidates():
    """Invariant 7: candidate list contains no duplicates."""
    tokens = ["machne", "pyhton", "databse", "larning", "tagor"]
    for t in tokens:
        candidates = engine.generator.generate(t, limit=30)
        assert len(candidates) == len(set(candidates)), f"Duplicate candidates generated for '{t}'"


def test_invariant_8_top_k_bound():
    """Invariant 8: top-K never returns more than configured K items."""
    k = engine.config.top_k
    res = engine.correct("machne larning databse")
    for tc in res["token_corrections"]:
        assert len(tc["candidates"]) <= k, f"Candidate count exceeded top_k {k}"
    assert len(res["suggestions"]) <= 5


def test_invariant_9_token_count_preservation():
    """Invariant 9: correction preserves token count and structure."""
    query = "python machne learning algorithms"
    res = engine.correct(query)
    orig_tokens = query.split()
    corrected_tokens = res["corrected_query"].split()
    assert len(orig_tokens) == len(corrected_tokens), (
        f"Token count changed from {len(orig_tokens)} to {len(corrected_tokens)}"
    )


def test_invariant_10_deterministic_output():
    """Invariant 10: deterministic input produces identical deterministic output."""
    query = "machne larning concepts"
    res1 = engine.correct(query)
    res2 = engine.correct(query)
    assert res1["corrected_query"] == res2["corrected_query"]
    assert res1["confidence"] == res2["confidence"]
    assert res1["suggestions"] == res2["suggestions"]
    assert res1["token_corrections"] == res2["token_corrections"]


def test_invariant_11_valid_words_not_unnecessarily_corrected():
    """Invariant 11: valid library vocabulary words are not unnecessarily corrected."""
    valid_terms = ["python", "algorithms", "database", "poetry", "machine", "learning", "networks"]
    for term in valid_terms:
        res = engine.correct(term)
        assert res["corrected_query"] == term, f"Valid term '{term}' was altered to '{res['corrected_query']}'"
        assert res["corrections"] == {}, f"Corrections registered for valid term '{term}'"


def test_invariant_12_empty_and_edge_inputs_never_crash():
    """Invariant 12: empty, whitespace, and extreme inputs never raise uncaught exceptions."""
    edge_cases = [
        "",
        " ",
        "   \t\n  ",
        "!!!",
        "???",
        "12345",
        "---",
        "a" * 500,
        "café crème naïve",
        "978-0-13-110362-7",
    ]
    for case in edge_cases:
        res = engine.correct(case)
        assert isinstance(res, dict)
        assert "corrected_query" in res
        assert "confidence" in res
