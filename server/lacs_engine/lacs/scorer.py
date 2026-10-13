from .models import CandidateScore


class CandidateScorer:
    DEFAULT_WEIGHTS = {
        "character": 0.25,
        "phonetic": 0.15,
        "library": 0.25,
        "context": 0.20,
        "frequency": 0.05,
        "history": 0.10,
    }

    def __init__(self, char, phonetic, library, context, history, weights=None):
        self.char = char
        self.phonetic = phonetic
        self.library = library
        self.context = context
        self.history = history
        self.weights = dict(weights or self.DEFAULT_WEIGHTS)
        total = sum(self.weights.values())
        if total <= 0:
            raise ValueError("scoring weights must have positive total")
        if abs(total - 1.0) > 1e-9:
            raise ValueError("scoring weights must sum to 1.0")

    def score(self, wrong, candidate, tokens, index):
        parts = {
            "character": self.char.score(wrong, candidate),
            "phonetic": self.phonetic.score(wrong, candidate),
            "library": self.library.score(candidate),
            "context": self.context.candidate_context_score(tokens, index, candidate),
            "frequency": self.library.frequency_score(candidate),
            "history": self.history.score(wrong, candidate),
        }
        total = sum(self.weights[k] * parts[k] for k in parts)
        final = max(0.0, min(1.0, total))
        return CandidateScore(
            candidate=candidate,
            character_score=parts["character"],
            phonetic_score=parts["phonetic"],
            library_score=parts["library"],
            context_score=parts["context"],
            frequency_score=parts["frequency"],
            history_score=parts["history"],
            final_score=final,
        )
