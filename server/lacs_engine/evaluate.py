"""
LACS (Library-Aware Contextual Spell Correction) — Evaluation Suite.

Reproducible evaluation script measuring:
1. Top-1 correction accuracy
2. Top-3 suggestion accuracy
3. Correct-query preservation rate
4. False correction rate (unwanted mutation of correct words)
5. Overcorrection rate
6. Latency distributions: mean, p50, p95, p99

Operates safely without mutating the live correction history.
"""

import argparse
import csv
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List
import numpy as np

# Ensure module path
LACS_ENGINE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(LACS_ENGINE_DIR))

from lacs import LACSAlgorithm, LACSConfig


def compute_file_hash(filepath: Path) -> str:
    """Compute SHA-256 hash of a file for reproducibility verification."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def evaluate_dataset(
    dataset_path: Path,
    vocabulary_path: Path,
    output_path: Path = None,
    history_path: Path = None,
) -> Dict[str, Any]:
    dataset_hash = compute_file_hash(dataset_path)

    # Initialize LACS algorithm with specified vocabulary and isolated history (no live mutation)
    config = LACSConfig()
    engine = LACSAlgorithm(
        library_csv=vocabulary_path,
        history_csv=history_path,  # Passed or None to avoid live history contamination
        config=config,
    )

    vocab_size = len(engine.vocabulary.vocabulary)

    queries = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            queries.append({
                "type": row.get("type", "mistake").strip().lower(),
                "original": row.get("original", "").strip(),
                "expected": row.get("expected", "").strip(),
                "error_type": row.get("error_type", "none").strip(),
            })

    all_latencies = []
    correct_queries = []
    mistake_queries = []

    # Run evaluation
    for item in queries:
        orig = item["original"]
        expected = item["expected"].lower()
        q_type = item["type"]

        t0 = time.perf_counter()
        result = engine.correct(orig)
        latency_ms = (time.perf_counter() - t0) * 1000
        all_latencies.append(latency_ms)

        corrected = (result.get("corrected_query") or "").strip().lower()
        suggestions = [s.strip().lower() for s in result.get("suggestions", [])]
        top3_pool = [corrected] + suggestions[:3]

        eval_item = {
            "original": orig,
            "expected": expected,
            "corrected": corrected,
            "confidence": result.get("confidence"),
            "confidence_level": result.get("confidence_level"),
            "top1_match": corrected == expected,
            "top3_match": expected in top3_pool,
            "latency_ms": latency_ms,
        }

        if q_type == "correct":
            # For correct queries, did it preserve unchanged?
            eval_item["preserved"] = (corrected == orig.lower())
            eval_item["false_correction"] = not eval_item["preserved"]
            correct_queries.append(eval_item)
        else:
            mistake_queries.append(eval_item)

    def calc_metrics(items: List[Dict[str, Any]], is_correct_set: bool = False) -> Dict[str, Any]:
        if not items:
            return {}
        n = len(items)
        top1 = sum(1 for x in items if x["top1_match"]) / n
        top3 = sum(1 for x in items if x["top3_match"]) / n
        lats = [x["latency_ms"] for x in items]

        res = {
            "queries": n,
            "top1_accuracy": round(top1, 4),
            "top3_accuracy": round(top3, 4),
            "average_latency_ms": round(float(np.mean(lats)), 3),
            "p50_latency_ms": round(float(np.percentile(lats, 50)), 3),
            "p95_latency_ms": round(float(np.percentile(lats, 95)), 3),
            "p99_latency_ms": round(float(np.percentile(lats, 99)), 3),
        }

        if is_correct_set:
            preserved_count = sum(1 for x in items if x.get("preserved", False))
            false_corr = sum(1 for x in items if x.get("false_correction", False))
            res["preservation_rate"] = round(preserved_count / n, 4)
            res["false_correction_rate"] = round(false_corr / n, 4)

        return res

    overall_items = correct_queries + mistake_queries
    overall_lats = [x["latency_ms"] for x in overall_items]

    results = {
        "metadata": {
            "dataset_path": str(dataset_path),
            "dataset_sha256": dataset_hash,
            "vocabulary_path": str(vocabulary_path),
            "vocabulary_size": vocab_size,
            "total_samples": len(queries),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "all_queries": {
            "queries": len(overall_items),
            "top1_accuracy": round(sum(1 for x in overall_items if x["top1_match"]) / len(overall_items), 4),
            "top3_accuracy": round(sum(1 for x in overall_items if x["top3_match"]) / len(overall_items), 4),
            "average_latency_ms": round(float(np.mean(overall_lats)), 3),
            "p50_latency_ms": round(float(np.percentile(overall_lats, 50)), 3),
            "p95_latency_ms": round(float(np.percentile(overall_lats, 95)), 3),
            "p99_latency_ms": round(float(np.percentile(overall_lats, 99)), 3),
        },
        "mistake_queries": calc_metrics(mistake_queries),
        "correct_queries": calc_metrics(correct_queries, is_correct_set=True),
    }

    print("\n" + "=" * 65)
    print("           LACS EVALUATION SUMMARY RESULTS")
    print("=" * 65)
    print(f"Dataset:            {dataset_path.name} (SHA-256: {dataset_hash[:12]}...)")
    print(f"Vocabulary Size:    {vocab_size} unique terms")
    print(f"Evaluated Samples:  {len(queries)} (Mistakes: {len(mistake_queries)}, Correct: {len(correct_queries)})")
    print("-" * 65)
    print(f"Top-1 Accuracy:     {results['all_queries']['top1_accuracy'] * 100:.2f}%")
    print(f"Top-3 Accuracy:     {results['all_queries']['top3_accuracy'] * 100:.2f}%")
    if correct_queries:
        print(f"Preservation Rate:  {results['correct_queries']['preservation_rate'] * 100:.2f}%")
        print(f"False Correction:   {results['correct_queries']['false_correction_rate'] * 100:.2f}%")
    print(f"Mean Latency:       {results['all_queries']['average_latency_ms']:.3f} ms")
    print(f"p50 Latency:        {results['all_queries']['p50_latency_ms']:.3f} ms")
    print(f"p95 Latency:        {results['all_queries']['p95_latency_ms']:.3f} ms")
    print(f"p99 Latency:        {results['all_queries']['p99_latency_ms']:.3f} ms")
    print("=" * 65 + "\n")

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"Evaluation results successfully saved to: {output_path}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Reproducible LACS Spell Correction Evaluation")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=LACS_ENGINE_DIR.parent / "lacs_data" / "evaluation_dataset.csv",
        help="Path to evaluation dataset CSV",
    )
    parser.add_argument(
        "--vocabulary",
        type=Path,
        default=LACS_ENGINE_DIR.parent / "lacs_data" / "library_books.csv",
        help="Path to library books CSV or vocabulary source",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=LACS_ENGINE_DIR.parent / "lacs_data" / "evaluation_results.json",
        help="Output path for JSON results",
    )
    args = parser.parse_args()

    evaluate_dataset(
        dataset_path=args.dataset,
        vocabulary_path=args.vocabulary,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
