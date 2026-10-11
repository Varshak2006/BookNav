from .edit_index import EditVariantIndex


class CandidateGenerator:
    def __init__(self, vocabulary, char_similarity, phonetic_similarity, config=None):
        self.vocabulary = vocabulary
        self.char = char_similarity
        self.phonetic = phonetic_similarity
        self.config = config
        self.edit_index = EditVariantIndex(
            max_edit_distance=getattr(config, "indexed_edit_distance", 2),
            max_token_length=getattr(config, "max_token_length", 40),
        )
        self.build_index()

    def rebuild_index(self):
        self.build_index()

    def build_index(self):
        self.edit_index.build_index(self.vocabulary.all_candidates())

    def add_word(self, word):
        self.edit_index.add_word(word)

    def remove_word(self, word):
        self.edit_index.remove_word(word)

    def _edit_variants(self, word):
        """Generate one-edit insertion, deletion, substitution and transposition variants."""
        letters = "abcdefghijklmnopqrstuvwxyz"
        variants = set()
        # deletion
        for i in range(len(word)):
            variants.add(word[:i] + word[i+1:])
        # insertion
        for i in range(len(word) + 1):
            for c in letters:
                variants.add(word[:i] + c + word[i:])
        # substitution
        for i in range(len(word)):
            for c in letters:
                if c != word[i]:
                    variants.add(word[:i] + c + word[i+1:])
        # transposition
        for i in range(len(word) - 1):
            if word[i] != word[i+1]:
                variants.add(word[:i] + word[i+1] + word[i] + word[i+2:])
        return variants

    def _prefix_suffix_score(self, word, candidate):
        if not word or not candidate:
            return 0.0
        prefix = 0
        for a, b in zip(word, candidate):
            if a != b:
                break
            prefix += 1
        suffix = 0
        for a, b in zip(word[::-1], candidate[::-1]):
            if a != b:
                break
            suffix += 1
        return min(1.0, (prefix + suffix) / max(len(word), len(candidate), 1))

    def _cheap_prefilter(self, word, candidate, is_direct_variant=False):
        if not candidate:
            return False
        if is_direct_variant:
            return True
        max_distance = self._max_edit_distance(word)
        if abs(len(word) - len(candidate)) > max_distance:
            return False
        if word[0:1] and candidate[0:1] and len(word) > 3 and len(candidate) > 3:
            if word[0] != candidate[0] and self.phonetic.key(word)[:1] != self.phonetic.key(candidate)[:1]:
                # Allow substitution/deletion/insertion at position 0, or transposition at position 0-1
                if (
                    word[1:] != candidate[1:]
                    and word[1:] != candidate
                    and word != candidate[1:]
                    and not (len(word) >= 2 and len(candidate) >= 2 and word[0] == candidate[1] and word[1] == candidate[0])
                    and self.char.distance(word[:min(len(word), 3)], candidate[:min(len(candidate), 3)]) > 1
                ):
                    return False
        return True

    def _max_edit_distance(self, word):
        if self.config is not None:
            return self.config.max_edit_distance_for(word)
        if len(word) <= 4:
            return 1
        return 2

    def generate(self, word, limit=25):
        word = word.lower()[: getattr(self.config, "max_token_length", 40)]
        limit = min(limit, getattr(self.config, "candidate_limit", limit))
        candidate_pool = set(self.edit_index.lookup_candidates(word))
        variants = self._edit_variants(word)
        direct_vocab_variants = {v for v in variants if self.vocabulary.contains(v)}
        candidate_pool.update(direct_vocab_variants)
        scored = []
        max_distance = self._max_edit_distance(word)
        for candidate in candidate_pool:
            is_direct_variant = candidate in variants
            if candidate == word or not self._cheap_prefilter(word, candidate, is_direct_variant=is_direct_variant):
                continue
            distance = self.char.distance(word, candidate)
            if distance > max_distance:
                continue
            cs = self.char.score(word, candidate)
            ps = self.phonetic.score(word, candidate)
            psf = self._prefix_suffix_score(word, candidate)
            edit_support = 1.0 if candidate in variants else 0.5
            # Retrieval only: final LACS score is calculated by CandidateScorer.
            retrieval = 0.55 * cs + 0.25 * ps + 0.10 * psf + 0.10 * edit_support
            if retrieval >= 0.28:
                scored.append((retrieval, cs, ps, candidate))
        scored.sort(key=lambda item: (-item[0], -item[1], -item[2], item[3]))
        return [c for _, _, _, c in scored[:limit]]
