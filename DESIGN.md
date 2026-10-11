# LACS module-by-module explanation

## 1. QueryNormalizer
Converts text to a stable lowercase representation, collapses repeated spaces, and tokenizes without destroying meaningful words.

## 2. VocabularyManager
Builds the domain vocabulary from titles, authors, categories, keywords and descriptions. It also maintains a small general English dictionary. Library terms have stronger relevance signals.

## 3. CandidateGenerator
Retrieves plausible candidates from an edit-variant index before applying
character and phonetic retrieval scoring. It does not scan the complete
vocabulary for every token and does not call a spell-correction package.

## 4. CharacterSimilarity
Implements normalized character edit similarity from scratch. This is only one feature.

## 5. PhoneticSimilarity
Creates a lightweight phonetic key and compares keys. It helps when pronunciation is similar.

## 6. ContextAnalyzer
Tests the candidate inside the complete query and its neighboring pairs. This is what lets a library query such as "ravindranath tagor" use contextual evidence.

## 7. LibraryRelevance
Rewards terms occurring in important library fields. Title and author are weighted strongly.

## 8. CorrectionHistory
Stores accepted corrections and turns historical acceptance frequency into another feature.

## 9. CandidateScorer
Computes:
FinalScore =
w1*Character +
w2*Phonetic +
w3*Library +
w4*Context +
w5*Frequency +
w6*History

## 10. ConfidenceDecision
Uses configurable thresholds:
- high: automatic correction
- medium: correction + alternatives
- low: suggestions without silent modification

High confidence also requires a score margin between the best and second-best
candidate. Raw scores are confidence scores, not calibrated probabilities.

## 11. LACSAlgorithm
Coordinates the entire pipeline and returns the required JSON-like result.
Corrections are represented internally by token position, so repeated
misspellings such as "machne machne" are handled independently.

## Complexity summary

| Component | Time | Space |
| --- | --- | --- |
| Levenshtein distance | O(m*n) | O(min(m,n)) |
| Edit index build | O(V * deletion_variants(term)) | O(V * deletion_variants(term)) |
| Candidate lookup | O(query_variants + matched_candidates) | O(matched_candidates) |
| Final scoring | O(C * feature_cost) | O(C) |

## Why this is library-specific

A general spell checker may prefer a common English word. LACS additionally asks:
- Is this term in the library?
- Is it an author/title/category/keyword?
- Does the candidate fit neighboring words?
- Does the complete corrected phrase occur in the library?
- Have users previously accepted this correction?

That domain evidence is the main reason the system is designed around library search.
