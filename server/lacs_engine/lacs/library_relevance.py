class LibraryRelevance:
    def __init__(self, vocabulary):
        self.vocabulary = vocabulary

    def score(self, candidate):
        return self.vocabulary.library_relevance(candidate)

    def frequency_score(self, candidate):
        freq = self.vocabulary.frequency(candidate)
        return freq / (freq + 5.0)
