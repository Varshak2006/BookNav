class ConfidenceDecision:
    def __init__(self, auto_threshold=0.47, medium_threshold=0.45, minimum_margin=0.03):
        self.auto_threshold = auto_threshold
        self.medium_threshold = medium_threshold
        self.minimum_margin = minimum_margin

    def decide(self, ranked):
        if not ranked:
            return {"level": "low", "confidence": 0.0, "score_margin": 0.0, "auto_correct": False}
        best = ranked[0][1]
        second = ranked[1][1] if len(ranked) > 1 else 0.0
        margin = best - second
        if best >= self.auto_threshold and margin >= self.minimum_margin:
            level = "high"
        elif best >= self.medium_threshold:
            level = "medium"
        else:
            level = "low"
        return {
            "level": level,
            "confidence": round(best, 4),
            "score_margin": round(margin, 4),
            "auto_correct": level == "high",
        }
