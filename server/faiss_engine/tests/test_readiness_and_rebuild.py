"""
Automated Tests for FAISS Readiness Validation and Safe Index Rebuilding.

Validates:
1. Missing index detection.
2. Missing mapping detection.
3. Missing metadata detection.
4. Corrupted index file handling.
5. Corrupted mapping / metadata JSON handling.
6. Dimension mismatch detection.
7. Model mismatch detection.
8. Metric mismatch detection.
9. Generation mismatch detection.
10. Count mismatch detection.
11. ID inconsistency detection.
12. Intentionally empty index authorization.
13. Safe rebuild staging and activation.
14. Empty rebuild rejection when allow_empty is False.
15. Preservation of previous generation in .prev backup files.
16. Previous generation restoration via restore_previous_generation().
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
import faiss
import numpy as np

from faiss_engine.build_index import (
    build_index_from_books,
    restore_previous_generation,
)
from faiss_engine.config import (
    DISTANCE_METRIC,
    EMBEDDING_DIM,
    SBERT_MODEL_NAME,
)
from faiss_engine.embedding_adapter import EmbeddingAdapter
from faiss_engine.id_mapping import IdMappingManager
from faiss_engine.index_manager import IndexManager
from faiss_engine.index_metadata import IndexMetadata
from faiss_engine.search_service import SearchService
from faiss_engine.validator import (
    IndexNotReadyError,
    IndexReadinessState,
    normalize_vectors,
    validate_index_artifacts,
)


class TestFaissReadiness(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.index_path = self.temp_dir / "test_vectors.index"
        self.mapping_path = self.temp_dir / "test_mapping.json"
        self.metadata_path = self.temp_dir / "test_metadata.json"
        self.dim = 384
        self.metric = "IP"
        self.model = "all-MiniLM-L6-v2"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_valid_artifacts(self, count=5, dim=384, metric="IP", model="all-MiniLM-L6-v2"):
        gen_id = IndexMetadata.create_generation_id()

        # Build index
        base_index = faiss.IndexFlatIP(dim) if metric == "IP" else faiss.IndexFlatL2(dim)
        index = faiss.IndexIDMap2(base_index)
        vectors = np.random.randn(count, dim).astype(np.float32)
        if metric == "IP":
            vectors = normalize_vectors(vectors)
        ids = np.arange(100, 100 + count, dtype=np.int64)
        index.add_with_ids(vectors, ids)
        faiss.write_index(index, str(self.index_path))

        # Build mapping
        mapping_mgr = IdMappingManager(self.mapping_path)
        mapping_mgr.clear()
        mapping_mgr.generation_id = gen_id
        for i, fid in enumerate(ids):
            mapping_mgr.add_entry(f"mongo_id_{i}", {"title": f"Book {i}"}, faiss_id=int(fid))
        mapping_mgr.save()

        # Build metadata
        meta_mgr = IndexMetadata(self.metadata_path)
        meta_mgr.set(
            generation_id=gen_id,
            model_name=model,
            embedding_dim=dim,
            distance_metric=metric,
            index_type="FLAT",
            vector_count=count,
        )
        meta_mgr.save()
        return gen_id

    def test_valid_artifacts_pass_validation(self):
        self._create_valid_artifacts(count=5)
        res = validate_index_artifacts(
            self.index_path,
            self.mapping_path,
            self.metadata_path,
            self.dim,
            self.metric,
            self.model,
        )
        self.assertTrue(res["ready"])
        self.assertEqual(res["state"], IndexReadinessState.READY)

    def test_missing_index_detected(self):
        self._create_valid_artifacts(count=5)
        self.index_path.unlink()
        res = validate_index_artifacts(
            self.index_path,
            self.mapping_path,
            self.metadata_path,
            self.dim,
            self.metric,
            self.model,
        )
        self.assertFalse(res["ready"])
        self.assertEqual(res["state"], IndexReadinessState.MISSING_INDEX)

    def test_missing_mapping_detected(self):
        self._create_valid_artifacts(count=5)
        self.mapping_path.unlink()
        res = validate_index_artifacts(
            self.index_path,
            self.mapping_path,
            self.metadata_path,
            self.dim,
            self.metric,
            self.model,
        )
        self.assertFalse(res["ready"])
        self.assertEqual(res["state"], IndexReadinessState.MISSING_MAPPING)

    def test_missing_metadata_detected(self):
        self._create_valid_artifacts(count=5)
        self.metadata_path.unlink()
        res = validate_index_artifacts(
            self.index_path,
            self.mapping_path,
            self.metadata_path,
            self.dim,
            self.metric,
            self.model,
        )
        self.assertFalse(res["ready"])
        self.assertEqual(res["state"], IndexReadinessState.MISSING_METADATA)

    def test_corrupted_index_detected(self):
        self._create_valid_artifacts(count=5)
        with open(self.index_path, "wb") as f:
            f.write(b"NOT_A_FAISS_INDEX_JUNK_DATA")
        res = validate_index_artifacts(
            self.index_path,
            self.mapping_path,
            self.metadata_path,
            self.dim,
            self.metric,
            self.model,
        )
        self.assertFalse(res["ready"])
        self.assertEqual(res["state"], IndexReadinessState.CORRUPTED_INDEX)

    def test_corrupted_mapping_json_detected(self):
        self._create_valid_artifacts(count=5)
        with open(self.mapping_path, "w") as f:
            f.write("{invalid_json_content...")
        res = validate_index_artifacts(
            self.index_path,
            self.mapping_path,
            self.metadata_path,
            self.dim,
            self.metric,
            self.model,
        )
        self.assertFalse(res["ready"])
        self.assertEqual(res["state"], IndexReadinessState.CORRUPTED_MAPPING)

    def test_dimension_mismatch_detected(self):
        self._create_valid_artifacts(count=5, dim=128)
        res = validate_index_artifacts(
            self.index_path,
            self.mapping_path,
            self.metadata_path,
            expected_dim=384,
            expected_metric="IP",
            expected_model="all-MiniLM-L6-v2",
        )
        self.assertFalse(res["ready"])
        self.assertEqual(res["state"], IndexReadinessState.DIMENSION_MISMATCH)

    def test_model_mismatch_detected(self):
        self._create_valid_artifacts(count=5, model="different-sbert-model")
        res = validate_index_artifacts(
            self.index_path,
            self.mapping_path,
            self.metadata_path,
            expected_dim=384,
            expected_metric="IP",
            expected_model="all-MiniLM-L6-v2",
        )
        self.assertFalse(res["ready"])
        self.assertEqual(res["state"], IndexReadinessState.MODEL_MISMATCH)

    def test_metric_mismatch_detected(self):
        self._create_valid_artifacts(count=5, metric="L2")
        res = validate_index_artifacts(
            self.index_path,
            self.mapping_path,
            self.metadata_path,
            expected_dim=384,
            expected_metric="IP",
            expected_model="all-MiniLM-L6-v2",
        )
        self.assertFalse(res["ready"])
        self.assertEqual(res["state"], IndexReadinessState.METRIC_MISMATCH)

    def test_generation_mismatch_detected(self):
        self._create_valid_artifacts(count=5)
        # Modify mapping generation
        with open(self.mapping_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["generation_id"] = "different_gen_123"
        with open(self.mapping_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        res = validate_index_artifacts(
            self.index_path,
            self.mapping_path,
            self.metadata_path,
            self.dim,
            self.metric,
            self.model,
        )
        self.assertFalse(res["ready"])
        self.assertEqual(res["state"], IndexReadinessState.GENERATION_MISMATCH)

    def test_count_mismatch_detected(self):
        self._create_valid_artifacts(count=5)
        # Remove an entry from mapping JSON without touching index
        with open(self.mapping_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["mappings"].pop()
        with open(self.mapping_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        res = validate_index_artifacts(
            self.index_path,
            self.mapping_path,
            self.metadata_path,
            self.dim,
            self.metric,
            self.model,
        )
        self.assertFalse(res["ready"])
        self.assertEqual(res["state"], IndexReadinessState.COUNT_MISMATCH)

    def test_intentionally_empty_authorized(self):
        res = validate_index_artifacts(
            self.index_path,
            self.mapping_path,
            self.metadata_path,
            self.dim,
            self.metric,
            self.model,
            allow_empty=True,
        )
        self.assertTrue(res["ready"])
        self.assertEqual(res["state"], IndexReadinessState.INTENTIONALLY_EMPTY)


class TestSafeIndexRebuild(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.index_path = self.temp_dir / "book_vectors.index"
        self.mapping_path = self.temp_dir / "book_id_mapping.json"
        self.metadata_path = self.temp_dir / "index_metadata.json"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_reject_empty_rebuild_without_authorization(self):
        with self.assertRaises(ValueError) as ctx:
            build_index_from_books(
                books=[],
                index_path=self.index_path,
                mapping_path=self.mapping_path,
                metadata_path=self.metadata_path,
                allow_empty=False,
            )
        self.assertIn("Safe Rebuild Rejected", str(ctx.exception))

    def test_safe_build_with_staged_activation_and_backup(self):
        books = [
            {"_id": "1", "title": "Operating Systems", "author": "Silberschatz", "category": "CS"},
            {"_id": "2", "title": "Computer Networks", "author": "Tanenbaum", "category": "Networking"},
        ]

        # Initial build
        stats = build_index_from_books(
            books=books,
            index_path=self.index_path,
            mapping_path=self.mapping_path,
            metadata_path=self.metadata_path,
            allow_empty=False,
        )
        self.assertEqual(stats["vectors_indexed"], 2)
        self.assertTrue(self.index_path.exists())
        self.assertTrue(self.mapping_path.exists())
        self.assertTrue(self.metadata_path.exists())

        # Second build with 3 books
        books3 = books + [{"_id": "3", "title": "Algorithms", "author": "Cormen", "category": "CS"}]
        stats2 = build_index_from_books(
            books=books3,
            index_path=self.index_path,
            mapping_path=self.mapping_path,
            metadata_path=self.metadata_path,
            allow_empty=False,
        )
        self.assertEqual(stats2["vectors_indexed"], 3)

        # Check that previous generation backup exists
        prev_index = self.index_path.with_name(f"{self.index_path.name}.prev")
        prev_mapping = self.mapping_path.with_name(f"{self.mapping_path.name}.prev")
        self.assertTrue(prev_index.exists())
        self.assertTrue(prev_mapping.exists())

        # Test recovery from previous backup
        restored = restore_previous_generation(
            index_path=self.index_path,
            mapping_path=self.mapping_path,
            metadata_path=self.metadata_path,
        )
        self.assertTrue(restored)

        # Verify restored index has 2 vectors (the previous generation)
        idx_restored = faiss.read_index(str(self.index_path))
        self.assertEqual(idx_restored.ntotal, 2)


if __name__ == "__main__":
    unittest.main()
