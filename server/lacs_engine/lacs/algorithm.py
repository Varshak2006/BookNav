import time
from .config import LACSConfig
from .normalizer import QueryNormalizer
from .vocabulary import VocabularyManager
from .character_similarity import CharacterSimilarity
from .phonetic_similarity import PhoneticSimilarity
from .candidate_generator import CandidateGenerator
from .context_analyzer import ContextAnalyzer
from .library_relevance import LibraryRelevance
from .history import CorrectionHistory
from .scorer import CandidateScorer
from .confidence import ConfidenceDecision
from .models import TokenCorrection

class LACSAlgorithm:
    """Library-Aware Contextual Spell Correction Algorithm (LACS)."""

    def __init__(self, library_csv, history_csv=None, weights=None, config=None, repository=None):
        if config is None:
            config = LACSConfig(weights=weights or LACSConfig().weights)
        elif weights is not None:
            config = LACSConfig(
                top_k=config.top_k,
                candidate_limit=config.candidate_limit,
                max_query_length=config.max_query_length,
                max_token_length=config.max_token_length,
                max_edit_distance_short=config.max_edit_distance_short,
                max_edit_distance_medium=config.max_edit_distance_medium,
                max_edit_distance_long=config.max_edit_distance_long,
                indexed_edit_distance=config.indexed_edit_distance,
                minimum_confidence=config.minimum_confidence,
                medium_confidence=config.medium_confidence,
                minimum_margin=config.minimum_margin,
                minimum_history_frequency=config.minimum_history_frequency,
                history_decay_days=config.history_decay_days,
                weights=weights,
                field_weights=config.field_weights,
            )
        self.config = config
        self.normalizer = QueryNormalizer()
        self.vocabulary = VocabularyManager(library_csv, config)
        self.char = CharacterSimilarity()
        self.phonetic = PhoneticSimilarity()
        self.generator = CandidateGenerator(self.vocabulary, self.char, self.phonetic, config)
        self.context = ContextAnalyzer(self.vocabulary)
        self.library = LibraryRelevance(self.vocabulary)
        self.history = CorrectionHistory(history_csv, config=config, repository=repository)
        self.scorer = CandidateScorer(
            self.char, self.phonetic, self.library,
            self.context, self.history, config.weights
        )
        self.confidence = ConfidenceDecision(
            auto_threshold=config.minimum_confidence,
            medium_threshold=config.medium_confidence,
            minimum_margin=config.minimum_margin,
        )

    def _rank_token_candidates(self, tokens, index):
        wrong = tokens[index]
        if self.vocabulary.contains(wrong):
            return []

        candidates = self.generator.generate(wrong, self.config.candidate_limit)
        ranked = []
        for candidate in candidates:
            ranked.append(self.scorer.score(wrong, candidate, tokens, index))
        ranked.sort(
            key=lambda item: (
                -item.final_score,
                -item.library_score,
                -item.character_score,
                -item.context_score,
                -item.frequency_score,
                item.candidate,
            )
        )
        return ranked

    def correct(self, query):
        start = time.perf_counter()
        original = query
        raw = "" if query is None else str(query)
        oversized = len(raw) > self.config.max_query_length
        normalized = self.normalizer.normalize(raw[: self.config.max_query_length])
        spans = self.normalizer.tokenize_with_spans(normalized)
        tokens = [span.text[: self.config.max_token_length] for span in spans]

        token_corrections = []
        suggestions_by_token = {}
        replacements = {}
        unresolved_tokens = []
        token_decisions = []

        # Iterative token correction: later context scoring sees earlier corrections.
        for i, token in enumerate(tokens):
            if self._should_skip_token(token):
                continue
            if self.vocabulary.contains(token):
                continue
            ranked = self._rank_token_candidates(tokens, i)
            if not ranked:
                unresolved_tokens.append(token)
                continue

            top_ranked = tuple(ranked[: self.config.top_k])
            suggestions_by_token[token] = [item.as_dict() for item in top_ranked]

            decision = self.confidence.decide([(item.candidate, item.final_score) for item in ranked])
            token_decisions.append(decision)
            corrected_token = ranked[0].candidate if decision["auto_correct"] else token
            correction = TokenCorrection(
                token_index=i,
                original_token=token,
                corrected_token=corrected_token,
                confidence=decision["confidence"],
                score_margin=decision["score_margin"],
                candidates=top_ranked,
                auto_corrected=decision["auto_correct"],
            )
            token_corrections.append(correction)
            if correction.auto_corrected:
                tokens[i] = correction.corrected_token
                replacements[i] = correction.corrected_token

        corrected = self.normalizer.rebuild_query(normalized, spans, replacements)

        # Complete-query alternatives: build alternatives token-by-token.
        query_suggestions = [corrected]
        for correction in token_corrections:
            for item in correction.candidates[:3]:
                alt_replacements = dict(replacements)
                alt_replacements[correction.token_index] = item.candidate
                candidate_query = self.normalizer.rebuild_query(normalized, spans, alt_replacements)
                if candidate_query not in query_suggestions:
                    query_suggestions.append(candidate_query)

        # Overall confidence: penalize unresolved tokens; valid query = 1.0.
        changed_scores = [c.confidence for c in token_corrections if c.auto_corrected]

        if unresolved_tokens:
            confidence = 0.0
        elif changed_scores:
            confidence = min(changed_scores)
        elif token_corrections:
            confidence = max(c.confidence for c in token_corrections)
        else:
            confidence = 1.0 if normalized else 0.0

        all_decided_tokens_auto = bool(token_decisions) and all(
            decision["auto_correct"] for decision in token_decisions
        )

        if (
            confidence >= self.confidence.auto_threshold
            and (not token_decisions or all_decided_tokens_auto)
        ):
            level = "high"
        elif confidence >= self.confidence.medium_threshold:
            level = "medium"
        else:
            level = "low"

        # If confidence is not high, preserve original rather than silently over-correct.
        if level != "high":
            final_query = normalized
        else:
            final_query = corrected

        elapsed_ms = (time.perf_counter() - start) * 1000

        return {
            "original_query": original,
            "corrected_query": final_query,
            "corrections": {
                c.original_token: c.corrected_token
                for c in token_corrections
                if c.auto_corrected
            },
            "token_corrections": [c.as_dict() for c in token_corrections],
            "confidence": round(confidence, 4),
            "confidence_level": level,
            "suggestions": query_suggestions[:5],
            "processing_time": round(elapsed_ms, 3),
            "token_details": suggestions_by_token,
            "truncated": oversized,
        }

    def sync_books(self, books):
        """Synchronize vocabulary entirely from an external list of book records."""
        self.vocabulary.sync_books(books)
        self.generator.rebuild_index()
        return len(self.vocabulary.vocabulary)

    def add_book(self, book):
        """Add a single book record dynamically to vocabulary and index."""
        new_words = self.vocabulary.add_record(book)
        for w in new_words:
            self.generator.add_word(w)
        return len(new_words)

    def update_book(self, old_book, new_book):
        """Update a book record dynamically in vocabulary and index."""
        if old_book:
            removed = self.vocabulary.remove_record(old_book)
            for w in removed:
                self.generator.remove_word(w)
        if new_book:
            new_words = self.vocabulary.add_record(new_book)
            for w in new_words:
                self.generator.add_word(w)

    def delete_book(self, book):
        """Delete a book record dynamically from vocabulary and index."""
        removed = self.vocabulary.remove_record(book)
        for w in removed:
            self.generator.remove_word(w)
        return len(removed)

    def accept_correction(self, wrong, correct):
        self.history.record(wrong, correct)

    @staticmethod
    def _should_skip_token(token):
        if not token:
            return True
        if token.isdigit():
            return True
        if any(ch.isdigit() for ch in token) and any(ch.isalpha() for ch in token):
            return True
        if len(token) >= 10 and token.replace("-", "").isdigit():
            return True
        return False
