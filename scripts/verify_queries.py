"""
End-to-End Query Verification Script for BookNav.
Evaluates the 10 mandatory queries through LACS, SBERT, FAISS, and MongoDB resolution.
"""

import os
import sys
import json
from pathlib import Path

# Offline mode for huggingface cache
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "server"))
sys.path.insert(0, str(ROOT_DIR / "server" / "lacs_engine"))
sys.path.insert(0, str(ROOT_DIR / "server" / "faiss_engine"))

from lacs import LACSAlgorithm
from faiss_engine.config import (
    DISTANCE_METRIC,
    EMBEDDING_DIM,
    INDEX_PATH,
    INDEX_TYPE,
    MAPPING_PATH,
    SBERT_MODEL_NAME,
)
from faiss_engine.embedding_adapter import EmbeddingAdapter
from faiss_engine.id_mapping import IdMappingManager
from faiss_engine.index_manager import IndexManager
from faiss_engine.search_service import SearchService
import pymongo

# Connect to MongoDB
mongo_client = pymongo.MongoClient("mongodb://localhost:27017/")
db = mongo_client["book"]
books_col = db["books"]

# Initialize LACS
lacs_vocab_path = ROOT_DIR / "server" / "lacs_data" / "library_books.csv"
lacs_history_path = ROOT_DIR / "server" / "lacs_data" / "correction_history.csv"
lacs_engine = LACSAlgorithm(library_csv=lacs_vocab_path, history_csv=lacs_history_path)

# Initialize FAISS components
id_mapping = IdMappingManager(mapping_path=MAPPING_PATH)
id_mapping.load()

index_manager = IndexManager(
    dimension=EMBEDDING_DIM,
    metric=DISTANCE_METRIC,
    index_type=INDEX_TYPE,
    index_path=INDEX_PATH,
)
index_manager.load()

embedding_adapter = EmbeddingAdapter(
    model_name=SBERT_MODEL_NAME,
    expected_dim=EMBEDDING_DIM,
)

faiss_service = SearchService(
    index_manager=index_manager,
    id_mapping=id_mapping,
    embedding_adapter=embedding_adapter,
)

queries = [
    ("harry poater", "Typo in popular title/author"),
    ("machine learning basics", "Multi-token semantic search query"),
    ("deep learning", "Standard technical domain query"),
    ("artificial intelligence", "Broad category/concept query"),
    ("operating systems", "Plural technical term query"),
    ("computer networks", "Standard system query"),
    ("Clean Code", "Exact correctly spelled existing title"),
    ("quantum culinary pastry mechanics", "No relevant books in library"),
    ("databases", "Plural word preservation test (check no false correction)"),
    ("cooding for begginers", "Misspelling of terms in larger collection")
]

print("=" * 80)
print("              SECTION 30: MANDATORY END-TO-END SEARCH QUERIES")
print("=" * 80)

results = []

for q, description in queries:
    # 1. LACS Stage
    lacs_res = lacs_engine.correct(q)
    conf_level = lacs_res.get("confidence_level", "low")
    corrected_q = lacs_res.get("corrected_query", q)
    correction_applied = (conf_level == "high" and corrected_q.lower() != q.lower())
    effective_q = corrected_q if correction_applied else q

    # 2. FAISS Vector Search
    faiss_res = faiss_service.search(query=effective_q, top_k=5)
    candidates = faiss_res.get("results", [])
    candidate_count = len(candidates)

    # 3. MongoDB Resolution
    book_ids = [c["book_id"] for c in candidates if c.get("book_id")]
    found_books = list(books_col.find({"_id": {"$in": [pymongo.collection.ObjectId(bid) for bid in book_ids if pymongo.collection.ObjectId.is_valid(bid)]}}))
    mongo_count = len(found_books)

    # Relevance threshold note
    top_score = candidates[0]["score"] if candidates else 0.0

    entry = {
        "query": q,
        "description": description,
        "lacs_decision": conf_level,
        "corrected_to": corrected_q if correction_applied else "-",
        "correction_applied": correction_applied,
        "effective_query": effective_q,
        "faiss_candidates": candidate_count,
        "mongo_records": mongo_count,
        "top_score": round(float(top_score), 4),
        "top_match_title": found_books[0]["title"] if found_books else "None"
    }
    results.append(entry)

    print(f"\nQuery: '{q}' [{description}]")
    print(f"  -> LACS Decision:      {conf_level.upper()} (applied={correction_applied}, corrected='{entry['corrected_to']}')")
    print(f"  -> Effective Query:   '{effective_q}'")
    print(f"  -> FAISS Candidates:  {candidate_count} (Top Score: {top_score:.4f})")
    print(f"  -> MongoDB Resolved:  {mongo_count} books")
    if found_books:
        print(f"  -> Top Book:          \"{found_books[0].get('title')}\" by {found_books[0].get('author')}")
    else:
        print(f"  -> Top Book:          None")

print("\n" + "=" * 80)
print("                          QUERY SUMMARY TABLE")
print("=" * 80)
print(f"{'Query':<30} | {'Decision':<8} | {'Corrected':<20} | {'FAISS':<5} | {'Mongo':<5} | {'Top Score':<9}")
print("-" * 80)
for r in results:
    print(f"{r['query']:<30} | {r['lacs_decision']:<8} | {r['corrected_to']:<20} | {r['faiss_candidates']:<5} | {r['mongo_records']:<5} | {r['top_score']:<9}")
print("=" * 80)
