import csv
import json
import statistics
import time
from pathlib import Path
from lacs import LACSAlgorithm
from lacs.character_similarity import CharacterSimilarity
from lacs.vocabulary import VocabularyManager

BASE = Path(__file__).resolve().parent
ENGINE = LACSAlgorithm(BASE/"data/library_books.csv", BASE/"data/correction_history.csv")
CHAR = CharacterSimilarity()
VOCAB = VocabularyManager(BASE/"data/library_books.csv")

def baseline_candidates(word, top=3):
    scored = []
    for candidate in VOCAB.all_candidates():
        if candidate == word:
            continue
        if abs(len(word) - len(candidate)) > 2:
            continue
        scored.append((CHAR.score(word, candidate), candidate))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [candidate for _, candidate in scored[:top]]

def baseline_correct(query):
    tokens = query.lower().split()
    corrected = []
    suggestions = []
    for token in tokens:
        if VOCAB.contains(token):
            corrected.append(token)
            continue
        candidates = baseline_candidates(token, 3)
        suggestions.extend(candidates)
        corrected.append(candidates[0] if candidates else token)
    return " ".join(corrected), suggestions

def percentile(values, pct):
    if not values:
        return 0.0
    values = sorted(values)
    index = min(len(values) - 1, int(round((pct / 100) * (len(values) - 1))))
    return values[index]

def query_accuracy(rows, engine_func):
    top1 = top3 = no_change = false_correction = overcorrection = 0
    latencies = []
    for row in rows:
        start = time.perf_counter()
        actual, suggestions = engine_func(row["original"])
        latencies.append((time.perf_counter() - start) * 1000)
        expected = row["expected"].lower()
        original = row["original"].lower()
        top1 += int(actual == expected)
        top3 += int(expected == actual or expected in suggestions[:3])
        no_change += int(row["type"] == "correct" and actual == original)
        false_correction += int(row["type"] == "correct" and actual != original)
        overcorrection += int(row["type"] == "correct" and actual != expected)
    count = len(rows) or 1
    return {
        "queries": len(rows),
        "top1_accuracy": top1 / count,
        "top3_accuracy": top3 / count,
        "no_change_accuracy": no_change / max(1, sum(1 for r in rows if r["type"] == "correct")),
        "false_correction_rate": false_correction / max(1, sum(1 for r in rows if r["type"] == "correct")),
        "overcorrection_rate": overcorrection / max(1, sum(1 for r in rows if r["type"] == "correct")),
        "average_latency_ms": statistics.mean(latencies) if latencies else 0.0,
        "p50_latency_ms": percentile(latencies, 50),
        "p95_latency_ms": percentile(latencies, 95),
        "p99_latency_ms": percentile(latencies, 99),
    }

def main():
    dataset_path = BASE / "data" / "evaluation_dataset.csv"
    if not dataset_path.exists():
        dataset_path = BASE / "data" / "test_queries.csv"
    rows=list(csv.DictReader(dataset_path.open(encoding="utf-8")))
    def lacs_func(query):
        out = ENGINE.correct(query)
        return out["corrected_query"].lower(), [x.lower() for x in out["suggestions"]]
    results = {
        "dataset": str(dataset_path),
        "all_queries": {
            "baseline_levenshtein": query_accuracy(rows, baseline_correct),
            "lacs": query_accuracy(rows, lacs_func),
        },
        "noisy_queries": {
            "baseline_levenshtein": query_accuracy([r for r in rows if r["type"] == "mistake"], baseline_correct),
            "lacs": query_accuracy([r for r in rows if r["type"] == "mistake"], lacs_func),
        },
        "correct_queries": {
            "baseline_levenshtein": query_accuracy([r for r in rows if r["type"] == "correct"], baseline_correct),
            "lacs": query_accuracy([r for r in rows if r["type"] == "correct"], lacs_func),
        },
    }
    out_path = BASE / "data" / "evaluation_results.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    print(f"Saved evaluation results to {out_path}")

if __name__ == "__main__":
    main()
