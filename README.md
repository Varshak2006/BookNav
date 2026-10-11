# LACS — Library-Aware Contextual Spell Correction Algorithm

LACS is a domain-specific spell correction pipeline designed specifically for library book search.

## Main objective

Correct mistakes in:
- book titles
- author names
- categories
- keywords
- natural-language library queries

Example:

`ravindranath tagor` → `rabindranath tagore`

`machne larning` → `machine learning`

## What is our own algorithm?

The OWN algorithmic contribution is the multi-signal decision pipeline:

1. Query normalization
2. Tokenization
3. Library + general vocabulary checking
4. Candidate generation using multiple manually implemented signals
5. Character similarity
6. Phonetic similarity
7. Library relevance
8. Complete-query context analysis
9. Frequency
10. Correction history
11. Weighted candidate scoring
12. Confidence-based decision

The final decision is NOT based only on edit distance.

### Own implementation

- `CharacterSimilarity`: normalized edit-distance calculation is implemented directly in Python.
- `PhoneticSimilarity`: lightweight phonetic key and similarity are implemented directly.
- `CandidateGenerator`: candidate retrieval logic is implemented directly.
- `ContextAnalyzer`: uses complete-query and neighboring library phrases.
- `LibraryRelevance`: gives different importance to title, author, category, keyword and description evidence.
- `CorrectionHistory`: learns accepted wrong→correct mappings.
- `CandidateScorer`: combines six normalized features using configurable weights.
- `ConfidenceDecision`: determines auto-correct vs suggestion behavior.
- `EditVariantIndex`: maps bounded edit variants to vocabulary terms so lookup does
  not scan every vocabulary word for every query token.
- `LACSAlgorithm`: orchestrates the complete pipeline.

## Supporting techniques

The project intentionally uses only Python standard-library facilities in the core implementation. No SymSpell/Norvig spell-correction function is called.

A future version may use an NLP library for tokenization or phonetic representation, but those would remain supporting components; the LACS decision logic would remain custom.

## Initial weights

These are configurable starting values, NOT claimed to be optimal:

- CharacterSimilarity: 0.25
- PhoneticSimilarity: 0.15
- LibraryRelevance: 0.25
- ContextScore: 0.20
- FrequencyScore: 0.05
- HistoricalScore: 0.10

Tune them using a held-out validation dataset.

## Run

Python 3.10+:

```bash
python main.py
```

Then enter:

```text
ravindranath tagor
harry pottr
machne larning
```

## Tests

```bash
python tests/test_lacs.py
```

## Evaluation

```bash
python evaluate.py
```

The evaluation compares LACS against a simple edit-distance baseline and writes
measured results to `data/evaluation_results.json`. The bundled dataset contains
100 queries. A larger final research dataset should include 100+ correct queries
and 100+ noisy queries before making broad performance claims.

## Benchmark

```bash
python benchmark.py
```

The benchmark builds synthetic vocabulary indexes at 1,000, 5,000, 10,000,
50,000, and 100,000 terms and writes measured latency/memory results to
`data/benchmark_results.json`.

## Data structures

- set: fast vocabulary membership
- Counter/dictionaries: term and field frequencies
- phrase map: contextual library phrase evidence
- correction-history map: accepted correction counts
- edit-variant index: bounded candidate retrieval before expensive scoring

## Output

Each call returns:

- `original_query`
- `corrected_query`
- `corrections`
- `confidence`
- `confidence_level`
- `suggestions`
- `processing_time`
- `token_details`
- `token_corrections`
- `truncated`

## Important research note

The starting weights and thresholds are engineering choices. They should be tuned and evaluated experimentally rather than described as optimal.

Likewise, LACS should only be claimed to outperform a baseline if the measured test results support that conclusion.

## BookNav integration

```python
from lacs import LACSAlgorithm

spell_corrector = LACSAlgorithm("data/library_books.csv", "data/correction_history.csv")
clean_query = spell_corrector.correct(user_query)["corrected_query"]
```

Call LACS before keyword extraction so the later BookNav search pipeline receives
a refined query while still preserving uncertain suggestions for the UI.
