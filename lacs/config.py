from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class LACSConfig:
    """Validated configuration for the LACS correction pipeline.

    The defaults are starting values for this library-search dataset, not
    statistically optimal constants.
    """

    top_k: int = 5
    candidate_limit: int = 50
    max_query_length: int = 300
    max_token_length: int = 40
    max_edit_distance_short: int = 1
    max_edit_distance_medium: int = 2
    max_edit_distance_long: int = 2
    indexed_edit_distance: int = 2
    minimum_confidence: float = 0.47
    medium_confidence: float = 0.45
    minimum_margin: float = 0.03
    minimum_history_frequency: int = 2
    history_decay_days: float = 365.0
    weights: Mapping[str, float] = field(default_factory=lambda: {
        "character": 0.25,
        "phonetic": 0.15,
        "library": 0.25,
        "context": 0.20,
        "frequency": 0.05,
        "history": 0.10,
    })
    field_weights: Mapping[str, float] = field(default_factory=lambda: {
        "title": 1.0,
        "author": 1.0,
        "category": 0.75,
        "keyword": 0.65,
        "description": 0.30,
    })

    def __post_init__(self) -> None:
        if self.top_k < 1:
            raise ValueError("top_k must be >= 1")
        if self.candidate_limit < self.top_k:
            raise ValueError("candidate_limit must be >= top_k")
        if self.max_query_length < 1:
            raise ValueError("max_query_length must be >= 1")
        if self.max_token_length < 1:
            raise ValueError("max_token_length must be >= 1")
        for name in (
            "max_edit_distance_short",
            "max_edit_distance_medium",
            "max_edit_distance_long",
            "indexed_edit_distance",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be >= 0")
        if not 0.0 <= self.medium_confidence <= self.minimum_confidence <= 1.0:
            raise ValueError("confidence thresholds must satisfy 0 <= medium <= minimum <= 1")
        if not 0.0 <= self.minimum_margin <= 1.0:
            raise ValueError("minimum_margin must be within [0, 1]")
        self._validate_weights("weights", self.weights)
        self._validate_weights("field_weights", self.field_weights, require_sum=False)

    @staticmethod
    def _validate_weights(name: str, weights: Mapping[str, float], require_sum: bool = True) -> None:
        if not weights:
            raise ValueError(f"{name} must not be empty")
        for key, value in weights.items():
            if value < 0.0:
                raise ValueError(f"{name}.{key} must be non-negative")
        total = sum(weights.values())
        if total <= 0.0:
            raise ValueError(f"{name} must have positive total weight")
        if require_sum and abs(total - 1.0) > 1e-9:
            raise ValueError(f"{name} must sum to 1.0; got {total:.6f}")

    def max_edit_distance_for(self, token: str) -> int:
        length = len(token)
        if length <= 4:
            return self.max_edit_distance_short
        if length <= 8:
            return self.max_edit_distance_medium
        return self.max_edit_distance_long
