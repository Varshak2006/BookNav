class ContextAnalyzer:
    def __init__(self, vocabulary):
        self.vocabulary = vocabulary

    def candidate_context_score(self, tokens, index, candidate):
        """Score how naturally a replacement fits the complete query.

        Evidence:
        - complete query phrase in library data
        - bigram/trigram neighboring compatibility
        - field-aware metadata phrase evidence
        - candidate already being a library term
        """
        trial = list(tokens)
        trial[index] = candidate
        phrase = " ".join(trial)

        phrase_score = self.vocabulary.phrase_relevance(phrase)
        neighbor = 0.0

        if index > 0:
            left = trial[index - 1]
            neighbor = max(
                neighbor,
                self.vocabulary.phrase_relevance(f"{left} {candidate}"),
                self.vocabulary.field_phrase_relevance(f"{left} {candidate}"),
            )

        if index + 1 < len(trial):
            right = trial[index + 1]
            neighbor = max(
                neighbor,
                self.vocabulary.phrase_relevance(f"{candidate} {right}"),
                self.vocabulary.field_phrase_relevance(f"{candidate} {right}"),
            )

        for start in range(max(0, index - 2), min(index + 1, len(trial) - 2) + 1):
            trigram = " ".join(trial[start:start + 3])
            neighbor = max(
                neighbor,
                self.vocabulary.phrase_relevance(trigram),
                self.vocabulary.field_phrase_relevance(trigram),
            )

        library_bonus = 1.0 if self.vocabulary.is_library_term(candidate) else 0.0
        unigram = self.vocabulary.library_relevance(candidate)
        return min(1.0, 0.35 * phrase_score + 0.35 * neighbor + 0.15 * unigram + 0.15 * library_bonus)
