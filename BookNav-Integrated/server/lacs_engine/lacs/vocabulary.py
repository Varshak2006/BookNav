from collections import Counter, defaultdict
import csv
from pathlib import Path
import re

class VocabularyManager:
    """Builds library-specific vocabulary and frequency/index structures."""

    STOPWORDS = {
        "a", "an", "and", "the", "of", "in", "on", "for", "to", "from", "with",
        "by", "or", "at",
    }

    def __init__(self, library_csv, config=None):
        self.library_csv = Path(library_csv)
        self.config = config
        self.vocabulary = set()
        self.general_dictionary = set(self._default_dictionary())
        self.term_frequency = Counter()
        self.field_frequency = defaultdict(Counter)
        self.field_ngram_frequency = defaultdict(Counter)
        self.term_fields = defaultdict(set)
        self.query_phrases = Counter()
        self.ngram_phrases = Counter()
        self._load()

    @staticmethod
    def _default_dictionary():
        return {
            "a","an","and","the","of","in","on","for","to","from","with","book",
            "books","about","author","by","find","search","show","me","give",
            "what","is","are","data","science","computer","programming","fiction",
            "poetry","fantasy","database","databases","networking","learning","machine",
            "algorithm","algorithms","python","artificial","intelligence",
            "operating","system","systems","deep","literature","indian"
        }

    TOKEN_RE = re.compile(r"[a-z0-9]+(?:['-][a-z0-9]+)*")

    def _parts(self, value):
        parts = []
        for p in self.TOKEN_RE.findall(str(value).lower()):
            if not p.isdigit():
                parts.append(p)
                if p.endswith("'s") and len(p) > 2:
                    parts.append(p[:-2])
        return parts

    def _significant_parts(self, parts):
        return [part for part in parts if part not in self.STOPWORDS]

    def _add_ngram_series(self, parts, field):
        for n in (2, 3):
            for j in range(len(parts) - n + 1):
                phrase = " ".join(parts[j:j+n])
                self.field_ngram_frequency[field][phrase] += 1
                self.ngram_phrases[phrase] += 1

    def _remove_ngram_series(self, parts, field):
        for n in (2, 3):
            for j in range(len(parts) - n + 1):
                phrase = " ".join(parts[j:j+n])
                if self.field_ngram_frequency[field][phrase] > 0:
                    self.field_ngram_frequency[field][phrase] -= 1
                if self.ngram_phrases[phrase] > 0:
                    self.ngram_phrases[phrase] -= 1

    def _add_field(self, value, field):
        if not value:
            return
        parts = self._parts(value)
        for p in parts:
            self.vocabulary.add(p)
            self.term_frequency[p] += 1
            self.field_frequency[field][p] += 1
            self.term_fields[p].add(field)
        self._add_ngram_series(parts, field)
        significant = self._significant_parts(parts)
        if significant != parts:
            self._add_ngram_series(significant, field)

    def add_record(self, row):
        """Add a book record dictionary into vocabulary structures."""
        if not isinstance(row, dict):
            return set()
        title = str(row.get("title") or "")
        author = str(row.get("author") or row.get("authors") or "")
        category = str(row.get("category") or row.get("subjects") or "")
        keywords = str(row.get("keywords") or "")
        description = str(row.get("description") or "")
        new_words = set()
        for value, field in [
            (title, "title"), (author, "author"),
            (category, "category"), (keywords, "keyword"),
            (description, "description")
        ]:
            if not value:
                continue
            parts = self._parts(value)
            for p in parts:
                if p not in self.vocabulary:
                    new_words.add(p)
                self.vocabulary.add(p)
                self.term_frequency[p] += 1
                self.field_frequency[field][p] += 1
                self.term_fields[p].add(field)
            self._add_ngram_series(parts, field)
            significant = self._significant_parts(parts)
            if significant != parts:
                self._add_ngram_series(significant, field)

        # Field-level phrases
        for phrase in (title, author, category):
            phrase = " ".join(phrase.lower().split())
            if phrase:
                self.query_phrases[phrase] += 1
                parts = phrase.split()
                for n in (2, 3):
                    for j in range(len(parts) - n + 1):
                        self.ngram_phrases[" ".join(parts[j:j+n])] += 1
                significant = self._significant_parts(parts)
                if significant != parts:
                    compact_phrase = " ".join(significant)
                    if compact_phrase:
                        self.query_phrases[compact_phrase] += 1
                    for n in (2, 3):
                        for j in range(len(significant) - n + 1):
                            self.ngram_phrases[" ".join(significant[j:j+n])] += 1

        # Compound cross-field phrase evidence (e.g. title + author co-occurrence)
        clean_title = " ".join(self._parts(title))
        clean_author = " ".join(self._parts(author))
        if clean_title and clean_author:
            for compound in (f"{clean_title} {clean_author}", f"{clean_author} {clean_title}"):
                self.query_phrases[compound] += 1
                compound_parts = compound.split()
                for n in (2, 3):
                    for j in range(len(compound_parts) - n + 1):
                        self.ngram_phrases[" ".join(compound_parts[j:j+n])] += 1

        return new_words

    def remove_record(self, row):
        """Remove a book record dictionary from vocabulary structures."""
        if not isinstance(row, dict):
            return set()
        title = str(row.get("title") or "")
        author = str(row.get("author") or row.get("authors") or "")
        category = str(row.get("category") or row.get("subjects") or "")
        keywords = str(row.get("keywords") or "")
        description = str(row.get("description") or "")
        removed_words = set()
        for value, field in [
            (title, "title"), (author, "author"),
            (category, "category"), (keywords, "keyword"),
            (description, "description")
        ]:
            if not value:
                continue
            parts = self._parts(value)
            for p in parts:
                if self.term_frequency[p] > 0:
                    self.term_frequency[p] -= 1
                    if self.term_frequency[p] == 0:
                        del self.term_frequency[p]
                        self.vocabulary.discard(p)
                        removed_words.add(p)
                if self.field_frequency[field][p] > 0:
                    self.field_frequency[field][p] -= 1
                    if self.field_frequency[field][p] == 0:
                        del self.field_frequency[field][p]
                        self.term_fields[p].discard(field)
            self._remove_ngram_series(parts, field)
            significant = self._significant_parts(parts)
            if significant != parts:
                self._remove_ngram_series(significant, field)

        for phrase in (title, author, category):
            phrase = " ".join(phrase.lower().split())
            if phrase:
                if self.query_phrases[phrase] > 0:
                    self.query_phrases[phrase] -= 1
                parts = phrase.split()
                for n in (2, 3):
                    for j in range(len(parts) - n + 1):
                        ng = " ".join(parts[j:j+n])
                        if self.ngram_phrases[ng] > 0:
                            self.ngram_phrases[ng] -= 1
                significant = self._significant_parts(parts)
                if significant != parts:
                    compact_phrase = " ".join(significant)
                    if compact_phrase and self.query_phrases[compact_phrase] > 0:
                        self.query_phrases[compact_phrase] -= 1
                    for n in (2, 3):
                        for j in range(len(significant) - n + 1):
                            ng = " ".join(significant[j:j+n])
                            if self.ngram_phrases[ng] > 0:
                                self.ngram_phrases[ng] -= 1

        clean_title = " ".join(self._parts(title))
        clean_author = " ".join(self._parts(author))
        if clean_title and clean_author:
            for compound in (f"{clean_title} {clean_author}", f"{clean_author} {clean_title}"):
                if self.query_phrases[compound] > 0:
                    self.query_phrases[compound] -= 1
                compound_parts = compound.split()
                for n in (2, 3):
                    for j in range(len(compound_parts) - n + 1):
                        ng = " ".join(compound_parts[j:j+n])
                        if self.ngram_phrases[ng] > 0:
                            self.ngram_phrases[ng] -= 1

        return removed_words

    def add_term_record(self, row):
        """Add a term record dictionary (from lacs_vocabulary.csv) into structures."""
        if not isinstance(row, dict):
            return
        term = str(row.get("term") or "").lower().strip()
        if not term:
            return
        freq = int(row.get("frequency", "1") or 1)
        source = str(row.get("source") or "library")
        fields = [f.strip() for f in str(row.get("fields") or "").split(";") if f.strip()]
        is_multi = str(row.get("term_type") or "") == "multiword" or " " in term

        if is_multi:
            self.query_phrases[term] += freq
            self.ngram_phrases[term] += freq
            for f in fields:
                self.field_ngram_frequency[f][term] += freq
        else:
            if source == "general":
                self.general_dictionary.add(term)
            else:
                self.vocabulary.add(term)
            self.term_frequency[term] += freq
            for f in fields:
                self.field_frequency[f][term] += freq
                self.term_fields[term].add(f)

    def sync_books(self, records):
        """Synchronize vocabulary entirely from an iterable of book records."""
        if not records:
            return set(self.vocabulary)
        self.vocabulary.clear()
        self.term_frequency.clear()
        self.field_frequency.clear()
        self.field_ngram_frequency.clear()
        self.term_fields.clear()
        self.query_phrases.clear()
        self.ngram_phrases.clear()
        for row in records:
            self.add_record(row)
        return set(self.vocabulary)

    def _load(self):
        if not self.library_csv:
            return
        p = Path(self.library_csv)
        if not p.exists() or not p.is_file():
            return
        with p.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            if "term" in fieldnames and "source" in fieldnames:
                for row in reader:
                    self.add_term_record(row)
            else:
                for row in reader:
                    self.add_record(row)

    def contains(self, word):
        w = word.lower()
        if w in self.vocabulary or w in self.general_dictionary:
            return True
        if w.endswith("'s") and len(w) > 2 and (w[:-2] in self.vocabulary or w[:-2] in self.general_dictionary):
            return True
        return False

    def is_library_term(self, word):
        w = word.lower()
        if w in self.vocabulary:
            return True
        if w.endswith("'s") and len(w) > 2 and w[:-2] in self.vocabulary:
            return True
        return False

    def frequency(self, word):
        w = word.lower()
        freq = self.term_frequency.get(w, 0)
        if freq == 0 and w.endswith("'s") and len(w) > 2:
            freq = self.term_frequency.get(w[:-2], 0)
        return freq

    def fields(self, word):
        w = word.lower()
        f = self.term_fields.get(w, set())
        if not f and w.endswith("'s") and len(w) > 2:
            f = self.term_fields.get(w[:-2], set())
        return f

    def library_relevance(self, word):
        """Weighted field relevance; title/author are intentionally stronger."""
        w = word.lower()
        weights = getattr(self.config, "field_weights", None) or {
            "title": 1.0, "author": 1.0, "category": 0.75,
            "keyword": 0.65, "description": 0.30
        }
        raw = sum(weights[f] * self.field_frequency[f].get(w, 0)
                  for f in weights)
        if raw == 0 and w.endswith("'s") and len(w) > 2:
            raw = sum(weights[f] * self.field_frequency[f].get(w[:-2], 0)
                      for f in weights)
        # Smoothly normalize without making frequency alone decisive.
        return raw / (raw + 3.0)

    def phrase_relevance(self, text):
        text = " ".join(text.lower().split())
        if not text:
            return 0.0
        count = self.query_phrases.get(text, 0)
        if count == 0:
            count = self.ngram_phrases.get(text, 0)
        return count / (count + 1.0)

    def field_phrase_relevance(self, text):
        text = " ".join(text.lower().split())
        if not text:
            return 0.0
        weights = getattr(self.config, "field_weights", None) or {
            "title": 1.0, "author": 1.0, "category": 0.75,
            "keyword": 0.65, "description": 0.30
        }
        raw = sum(weights[field] * self.field_ngram_frequency[field].get(text, 0)
                  for field in weights)
        return raw / (raw + 2.0)

    def all_candidates(self):
        return self.vocabulary | self.general_dictionary
