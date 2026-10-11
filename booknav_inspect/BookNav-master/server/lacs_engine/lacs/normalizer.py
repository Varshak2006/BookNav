import re
import unicodedata
from .models import TokenSpan

class QueryNormalizer:
    """Conservative normalization that preserves meaningful title/name information."""

    TOKEN_RE = re.compile(r"[a-z0-9]+(?:['-][a-z0-9]+)*")

    def normalize(self, text: str) -> str:
        text = unicodedata.normalize("NFKC", text or "")
        text = text.lower().strip()
        text = re.sub(r"\s+", " ", text)
        return text

    def tokenize(self, text: str):
        # Keep apostrophes/hyphens inside words where possible.
        return [span.text for span in self.tokenize_with_spans(text)]

    def tokenize_with_spans(self, text: str) -> list[TokenSpan]:
        return [
            TokenSpan(i, match.group(0), match.start(), match.end())
            for i, match in enumerate(self.TOKEN_RE.finditer(text.lower()))
        ]

    def rebuild_query(self, normalized_text: str, spans: list[TokenSpan], replacements: dict[int, str]) -> str:
        if not spans:
            return normalized_text
        pieces = []
        cursor = 0
        for span in spans:
            pieces.append(normalized_text[cursor:span.start])
            pieces.append(replacements.get(span.index, span.text))
            cursor = span.end
        pieces.append(normalized_text[cursor:])
        return "".join(pieces)
