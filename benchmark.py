import csv
import json
import statistics
import time
import tracemalloc
from pathlib import Path

from lacs import LACSAlgorithm
from lacs.config import LACSConfig


BASE = Path(__file__).resolve().parent
VOCAB_SIZES = (1000, 5000, 10000, 50000, 100000)
QUERIES = (
    "machne larning",
    "harry pottr",
    "ravindranath tagor",
    "database systm concepts",
    "python programming",
)


def load_seed_words():
    words = set()
    with (BASE / "data" / "library_books.csv").open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for value in row.values():
                for token in str(value).lower().replace(",", " ").replace(".", " ").split():
                    clean = "".join(ch for ch in token if ch.isalnum())
                    if clean:
                        words.add(clean)
    return sorted(words)


def synthetic_words(target_size):
    words = load_seed_words()
    i = 0
    while len(words) < target_size:
        words.append(f"term{i:06d}")
        i += 1
    return words[:target_size]


def percentile(values, pct):
    values = sorted(values)
    index = min(len(values) - 1, int(round((pct / 100) * (len(values) - 1))))
    return values[index]


def benchmark_size(size):
    config = LACSConfig()
    tracemalloc.start()
    engine = LACSAlgorithm(BASE / "data" / "library_books.csv", BASE / "data" / "correction_history.csv", config=config)
    engine.generator.edit_index.build_index(synthetic_words(size))
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    candidate_times = []
    total_times = []
    candidate_counts = []
    scoring_times = []
    for query in QUERIES:
        first_token = query.split()[0]
        start = time.perf_counter()
        candidates = engine.generator.generate(first_token)
        candidate_times.append((time.perf_counter() - start) * 1000)
        candidate_counts.append(len(candidates))

        start = time.perf_counter()
        out = engine.correct(query)
        total_times.append((time.perf_counter() - start) * 1000)
        scoring_times.append(max(0.0, out["processing_time"] - candidate_times[-1]))

    return {
        "vocabulary_size": size,
        "candidate_generation_avg_ms": statistics.mean(candidate_times),
        "scoring_avg_ms": statistics.mean(scoring_times),
        "total_avg_ms": statistics.mean(total_times),
        "total_p50_ms": percentile(total_times, 50),
        "total_p95_ms": percentile(total_times, 95),
        "total_p99_ms": percentile(total_times, 99),
        "peak_memory_bytes": peak_bytes,
        "average_candidates": statistics.mean(candidate_counts),
    }


def main():
    results = [benchmark_size(size) for size in VOCAB_SIZES]
    out_path = BASE / "data" / "benchmark_results.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    print(f"Saved benchmark results to {out_path}")


if __name__ == "__main__":
    main()
