from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class TokenSpan:
    """A token occurrence and its character offsets in the normalized query."""

    index: int
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class CandidateScore:
    """Normalized score components for one correction candidate."""

    candidate: str
    character_score: float
    phonetic_score: float
    library_score: float
    context_score: float
    frequency_score: float
    history_score: float
    final_score: float

    @property
    def features(self) -> Mapping[str, float]:
        return {
            "character": self.character_score,
            "phonetic": self.phonetic_score,
            "library": self.library_score,
            "context": self.context_score,
            "frequency": self.frequency_score,
            "history": self.history_score,
        }

    def as_dict(self) -> dict:
        return {
            "candidate": self.candidate,
            "score": round(self.final_score, 4),
            "features": {k: round(v, 4) for k, v in self.features.items()},
        }


@dataclass(frozen=True)
class TokenCorrection:
    """Correction decision for a specific token occurrence."""

    token_index: int
    original_token: str
    corrected_token: str
    confidence: float
    score_margin: float
    candidates: tuple[CandidateScore, ...] = field(default_factory=tuple)
    auto_corrected: bool = False

    def as_dict(self) -> dict:
        return {
            "token_index": self.token_index,
            "original_token": self.original_token,
            "corrected_token": self.corrected_token,
            "confidence": round(self.confidence, 4),
            "score_margin": round(self.score_margin, 4),
            "auto_corrected": self.auto_corrected,
            "candidates": [c.as_dict() for c in self.candidates],
        }
