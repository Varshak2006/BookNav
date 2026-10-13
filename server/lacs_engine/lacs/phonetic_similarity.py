class PhoneticSimilarity:
    """Custom phonetic similarity based on manually defined phonetic groups.

    This is intentionally a lightweight supporting technique, not a ready-made
    spell-correction function.
    """

    GROUPS = {
        "0": "aeiou",
        "1": "bp",
        "2": "ckq",
        "3": "dt",
        "4": "l",
        "5": "mn",
        "6": "r",
        "7": "fvw",
        "8": "g",
        "9": "h",
        "x": "sz",
        "y": "j",
    }

    def key(self, word):
        word = "".join(c for c in word.lower() if c.isalpha())
        if not word:
            return ""
        result = []
        previous = None
        for ch in word:
            code = next((k for k, chars in self.GROUPS.items() if ch in chars), ch)
            if code == previous:
                continue
            result.append(code)
            previous = code
        return "".join(result)

    def score(self, a, b):
        ka, kb = self.key(a), self.key(b)
        if not ka and not kb:
            return 1.0
        if not ka or not kb:
            return 0.0
        # Compare keys using the same independently implemented normalized distance.
        m, n = len(ka), len(kb)
        prev = list(range(n + 1))
        for i, ca in enumerate(ka, 1):
            cur = [i]
            for j, cb in enumerate(kb, 1):
                cur.append(min(cur[j-1] + 1, prev[j] + 1,
                               prev[j-1] + (ca != cb)))
            prev = cur
        d = prev[-1]
        return max(0.0, 1.0 - d / max(m, n))
