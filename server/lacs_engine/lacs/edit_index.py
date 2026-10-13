from collections import defaultdict
from typing import Iterable


class EditVariantIndex:
    """Deletion-variant index for bounded custom candidate lookup.

    Build time is O(V * variants(word)) for V vocabulary terms. Lookup generates
    bounded variants for the query token and unions matching buckets before the
    expensive scoring stage. The index does not claim constant-time lookup.
    """

    def __init__(self, max_edit_distance: int = 2, max_token_length: int = 40):
        self.max_edit_distance = max_edit_distance
        self.max_token_length = max_token_length
        self._index: dict[str, set[str]] = defaultdict(set)
        self._words: set[str] = set()

    def build_index(self, words: Iterable[str]) -> None:
        self._index.clear()
        self._words.clear()
        for word in words:
            self.add_word(word)

    def add_word(self, word: str) -> None:
        clean = self._clean(word)
        if not clean:
            return
        self._words.add(clean)
        for variant in self._delete_variants(clean):
            self._index[variant].add(clean)

    def remove_word(self, word: str) -> None:
        clean = self._clean(word)
        if clean not in self._words:
            return
        self._words.remove(clean)
        for variant in self._delete_variants(clean):
            bucket = self._index.get(variant)
            if not bucket:
                continue
            bucket.discard(clean)
            if not bucket:
                del self._index[variant]

    def lookup_candidates(self, word: str) -> set[str]:
        clean = self._clean(word)
        if not clean:
            return set()
        candidates = set()
        for variant in self._delete_variants(clean):
            candidates.update(self._index.get(variant, ()))
        if clean in self._words:
            candidates.add(clean)
        return candidates

    def _clean(self, word: str) -> str:
        return (word or "").lower()[: self.max_token_length]

    def _delete_variants(self, word: str) -> set[str]:
        variants = {word}
        current = {word}
        for _ in range(self.max_edit_distance):
            next_level = set()
            for value in current:
                if not value:
                    continue
                for i in range(len(value)):
                    next_level.add(value[:i] + value[i + 1 :])
            next_level -= variants
            variants.update(next_level)
            current = next_level
        return variants
