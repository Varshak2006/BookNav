class CharacterSimilarity:
    """Own character-level similarity implementation.

    We calculate a normalized Damerau-Levenshtein-style distance ourselves
    (supporting insertions, deletions, substitutions, and adjacent transpositions)
    and expose it only as one feature of LACS. It is never the sole decision criterion.
    """

    def distance(self, a, b):
        a, b = a.lower(), b.lower()
        if a == b:
            return 0
        if not a:
            return len(b)
        if not b:
            return len(a)

        len_a, len_b = len(a), len(b)
        dp = [[0] * (len_b + 1) for _ in range(len_a + 1)]

        for i in range(len_a + 1):
            dp[i][0] = i
        for j in range(len_b + 1):
            dp[0][j] = j

        for i in range(1, len_a + 1):
            for j in range(1, len_b + 1):
                cost = 0 if a[i - 1] == b[j - 1] else 1
                dp[i][j] = min(
                    dp[i - 1][j] + 1,       # deletion
                    dp[i][j - 1] + 1,       # insertion
                    dp[i - 1][j - 1] + cost # substitution
                )
                if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                    dp[i][j] = min(dp[i][j], dp[i - 2][j - 2] + 1) # transposition

        return dp[len_a][len_b]

    def score(self, a, b):
        if not a and not b:
            return 1.0
        d = self.distance(a, b)
        return max(0.0, 1.0 - d / max(len(a), len(b), 1))
