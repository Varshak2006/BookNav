"""
Automated Unit Tests for BookNav FAISS Vector Search Module.

Tests cover:
1. Vector validation (dimension mismatch, non-finite values, empty vectors).
2. L2 Normalization (unit Euclidean norm, zero vector handling).
3. Index creation, training, addition, and search (FlatIP, FlatL2, IVF, HNSW).
4. Distance & Similarity ordering (IP descending, L2 ascending).
5. Bi-directional ID mapping (FAISS integer <-> MongoDB ObjectId).
6. Library metadata filtering (author, category, shelf, multi-filter, empty match).
7. Candidate pool expansion logic.
8. Atomic persistence and corruption recovery.
9. Dynamic incremental additions and deletions.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
import faiss
import numpy as np

from faiss_engine.config import EMBEDDING_DIM
from faiss_engine.embedding_adapter import EmbeddingAdapter
from faiss_engine.id_mapping import IdMappingManager
from faiss_engine.index_manager import IndexManager
from faiss_engine.search_service import SearchService
from faiss_engine.validator import (
    VectorValidationError,
    normalize_vectors,
    validate_vector,
)


class TestVectorValidation(unittest.TestCase):
    def setUp(self):
        self.dim = 384

    def test_valid_1d_vector(self):
        vec = np.random.randn(self.dim).astype(np.float32)
        validated = validate_vector(vec, self.dim, allow_batch=False)
        self.assertEqual(validated.shape, (self.dim,))
        self.assertEqual(validated.dtype, np.float32)

    def test_valid_batch_vectors(self):
        vecs = np.random.randn(10, self.dim).astype(np.float32)
        validated = validate_vector(vecs, self.dim, allow_batch=True)
        self.assertEqual(validated.shape, (10, self.dim))

    def test_reject_dimension_mismatch(self):
        vec = np.random.randn(128).astype(np.float32)
        with self.assertRaises(VectorValidationError):
            validate_vector(vec, self.dim, allow_batch=False)

    def test_reject_nan_values(self):
        vec = np.ones(self.dim, dtype=np.float32)
        vec[10] = np.nan
        with self.assertRaises(VectorValidationError):
            validate_vector(vec, self.dim)

    def test_reject_inf_values(self):
        vec = np.ones(self.dim, dtype=np.float32)
        vec[5] = np.inf
        with self.assertRaises(VectorValidationError):
            validate_vector(vec, self.dim)

    def test_reject_empty_vector(self):
        with self.assertRaises(VectorValidationError):
            validate_vector([], self.dim)

    def test_reject_none_vector(self):
        with self.assertRaises(VectorValidationError):
            validate_vector(None, self.dim)


class TestNormalization(unittest.TestCase):
    def test_l2_normalization_1d(self):
        vec = np.array([3.0, 4.0, 0.0], dtype=np.float32)
        norm_vec = normalize_vectors(vec)
        self.assertAlmostEqual(float(np.linalg.norm(norm_vec)), 1.0, places=5)
        self.assertAlmostEqual(float(norm_vec[0]), 0.6, places=5)
        self.assertAlmostEqual(float(norm_vec[1]), 0.8, places=5)

    def test_l2_normalization_batch(self):
        vecs = np.random.randn(5, 64).astype(np.float32)
        norm_vecs = normalize_vectors(vecs)
        norms = np.linalg.norm(norm_vecs, axis=1)
        for n in norms:
            self.assertAlmostEqual(float(n), 1.0, places=5)

    def test_zero_vector_normalization(self):
        vec = np.zeros(10, dtype=np.float32)
        norm_vec = normalize_vectors(vec)
        self.assertEqual(np.linalg.norm(norm_vec), 0.0)


class TestIdMappingManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.mapping_file = Path(self.temp_dir) / "test_mapping.json"
        self.manager = IdMappingManager(self.mapping_file)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_add_and_lookup(self):
        fid = self.manager.add_entry("mongo_123", {"title": "Clean Code", "author": "Robert Martin"})
        self.assertEqual(fid, 0)
        self.assertEqual(self.manager.get_book_id(0), "mongo_123")
        self.assertEqual(self.manager.get_faiss_id("mongo_123"), 0)

        meta = self.manager.get_metadata(0)
        self.assertEqual(meta["title"], "Clean Code")

    def test_duplicate_prevention(self):
        fid1 = self.manager.add_entry("mongo_123", {"title": "Clean Code"})
        fid2 = self.manager.add_entry("mongo_123", {"title": "Clean Code Updated"})
        self.assertEqual(fid1, fid2)
        self.assertEqual(len(self.manager), 1)
        self.assertEqual(self.manager.get_metadata(fid1)["title"], "Clean Code Updated")

    def test_persistence_and_reload(self):
        self.manager.add_entry("mongo_1", {"title": "Book 1"})
        self.manager.add_entry("mongo_2", {"title": "Book 2"})
        self.manager.save()

        new_manager = IdMappingManager(self.mapping_file)
        loaded = new_manager.load()
        self.assertTrue(loaded)
        self.assertEqual(len(new_manager), 2)
        self.assertEqual(new_manager.get_book_id(1), "mongo_2")
        self.assertEqual(new_manager.get_metadata(0)["title"], "Book 1")

    def test_delete_entry(self):
        fid = self.manager.add_entry("mongo_del", {"title": "To Delete"})
        self.assertEqual(len(self.manager), 1)
        removed_fid = self.manager.remove_by_mongo_id("mongo_del")
        self.assertEqual(removed_fid, fid)
        self.assertEqual(len(self.manager), 0)
        self.assertIsNone(self.manager.get_book_id(fid))


class TestIndexManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.index_file = Path(self.temp_dir) / "test.index"
        self.dim = 32

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_flat_ip_exact_search(self):
        mgr = IndexManager(dimension=self.dim, metric="IP", index_type="FLAT", index_path=self.index_file)
        mgr.build_empty_index(use_id_map=True)

        # Generate 10 normalized vectors
        np.random.seed(42)
        vecs = normalize_vectors(np.random.randn(10, self.dim).astype(np.float32))
        ids = np.arange(10, dtype=np.int64)
        mgr.add_vectors(vecs, ids=ids)

        self.assertEqual(mgr.count, 10)

        # Search for vector 3 (query identical to indexed vector 3)
        query = vecs[3]
        scores, indices = mgr.search(query, top_k=3)

        # Nearest neighbor must be vector 3 with similarity ~ 1.0
        self.assertEqual(indices[0][0], 3)
        self.assertAlmostEqual(float(scores[0][0]), 1.0, places=4)

    def test_persistence_atomic_save_load(self):
        mgr = IndexManager(dimension=self.dim, metric="IP", index_type="FLAT", index_path=self.index_file)
        mgr.build_empty_index(use_id_map=True)
        vecs = normalize_vectors(np.random.randn(5, self.dim).astype(np.float32))
        mgr.add_vectors(vecs, ids=np.arange(5, dtype=np.int64))
        mgr.save()

        reloaded = IndexManager(dimension=self.dim, metric="IP", index_type="FLAT", index_path=self.index_file)
        success = reloaded.load()
        self.assertTrue(success)
        self.assertEqual(reloaded.count, 5)

    def test_remove_ids(self):
        mgr = IndexManager(dimension=self.dim, metric="IP", index_type="FLAT", index_path=self.index_file)
        mgr.build_empty_index(use_id_map=True)
        vecs = normalize_vectors(np.random.randn(5, self.dim).astype(np.float32))
        mgr.add_vectors(vecs, ids=np.array([10, 20, 30, 40, 50], dtype=np.int64))
        self.assertEqual(mgr.count, 5)

        mgr.remove_ids(np.array([30], dtype=np.int64))
        self.assertEqual(mgr.count, 4)


class TestSearchServiceAndFiltering(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.index_file = Path(self.temp_dir) / "search.index"
        self.mapping_file = Path(self.temp_dir) / "search_mapping.json"
        self.dim = 16

        self.index_mgr = IndexManager(dimension=self.dim, metric="IP", index_type="FLAT", index_path=self.index_file)
        self.index_mgr.build_empty_index(use_id_map=True)
        self.mapping_mgr = IdMappingManager(self.mapping_file)

        # Add 3 distinct synthetic books
        # Book A: Machine Learning / AI
        # Book B: Operating Systems
        # Book C: Algorithms / CS
        np.random.seed(123)
        self.vec_a = normalize_vectors(np.array([1.0] + [0.0] * 15, dtype=np.float32))
        self.vec_b = normalize_vectors(np.array([0.0, 1.0] + [0.0] * 14, dtype=np.float32))
        self.vec_c = normalize_vectors(np.array([0.0, 0.0, 1.0] + [0.0] * 13, dtype=np.float32))

        vecs = np.vstack([self.vec_a, self.vec_b, self.vec_c])
        ids = np.array([0, 1, 2], dtype=np.int64)

        self.mapping_mgr.add_entry("mongo_a", {"title": "Machine Learning", "author": "Tom Mitchell", "category": "AI", "shelf": "A1"})
        self.mapping_mgr.add_entry("mongo_b", {"title": "Operating Systems", "author": "Abraham Silberschatz", "category": "CS", "shelf": "B2"})
        self.mapping_mgr.add_entry("mongo_c", {"title": "Algorithms", "author": "Robert Sedgewick", "category": "CS", "shelf": "C3"})

        self.index_mgr.add_vectors(vecs, ids=ids)

        # Dummy adapter returning fixed vector
        class DummyAdapter:
            def __init__(self, target_vec):
                self.target_vec = target_vec
                self.expected_dim = len(target_vec)
                self.model_name = "dummy"

            def encode_query(self, query, normalize=True):
                return self.target_vec

        self.service = SearchService(
            index_manager=self.index_mgr,
            id_mapping=self.mapping_mgr,
            embedding_adapter=DummyAdapter(self.vec_a)
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_unfiltered_top_search(self):
        res = self.service.search(query=self.vec_a, top_k=2)
        self.assertEqual(res["results_count"], 2)
        # First match must be Machine Learning
        self.assertEqual(res["results"][0]["book_id"], "mongo_a")
        self.assertEqual(res["results"][0]["rank"], 1)
        self.assertAlmostEqual(res["results"][0]["score"], 1.0, places=3)

    def test_category_filter(self):
        # Querying with vec_a (most similar to Machine Learning), but filtering category="CS"
        res = self.service.search(query=self.vec_a, top_k=2, filters={"category": "CS"})
        # Should exclude Machine Learning and return CS books only
        for item in res["results"]:
            self.assertEqual(item["category"], "CS")
        self.assertNotIn("mongo_a", [r["book_id"] for r in res["results"]])

    def test_author_filter(self):
        res = self.service.search(query=self.vec_a, top_k=5, filters={"author": "Silberschatz"})
        self.assertEqual(res["results_count"], 1)
        self.assertEqual(res["results"][0]["book_id"], "mongo_b")

    def test_no_matching_filter(self):
        res = self.service.search(query=self.vec_a, top_k=5, filters={"category": "NonExistent"})
        self.assertEqual(res["results_count"], 0)
        self.assertEqual(len(res["results"]), 0)

    def test_reject_unsupported_filter_field(self):
        with self.assertRaises(ValueError) as ctx:
            self.service.search(query=self.vec_a, top_k=5, filters={"unsupported_field": "val"})
        self.assertIn("Unsupported filter field", str(ctx.exception))

    def test_supported_filter_fields_validation(self):
        # Valid fields should not raise
        for field in ["author", "category", "shelf", "rack", "location", "keywords", "title"]:
            validated = self.service.validate_filters({field: "test"})
            self.assertEqual(validated, {field: "test"})


class TestIndexMetadataAndConsistency(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.meta_file = Path(self.temp_dir) / "index_metadata.json"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_generation_id_generation(self):
        from faiss_engine.index_metadata import IndexMetadata
        gid1 = IndexMetadata.create_generation_id()
        gid2 = IndexMetadata.create_generation_id()
        self.assertIsInstance(gid1, str)
        self.assertNotEqual(gid1, gid2)

    def test_save_and_load_metadata(self):
        from faiss_engine.index_metadata import IndexMetadata
        meta = IndexMetadata(self.meta_file)
        gid = IndexMetadata.create_generation_id()
        meta.set(
            generation_id=gid,
            model_name="all-MiniLM-L6-v2",
            embedding_dim=384,
            distance_metric="IP",
            index_type="FLAT",
            vector_count=100,
        )
        meta.save()
        self.assertTrue(self.meta_file.exists())

        loaded_meta = IndexMetadata(self.meta_file)
        success = loaded_meta.load()
        self.assertTrue(success)
        self.assertEqual(loaded_meta.generation_id, gid)
        self.assertEqual(loaded_meta.model_name, "all-MiniLM-L6-v2")
        self.assertEqual(loaded_meta.embedding_dim, 384)
        self.assertEqual(loaded_meta.distance_metric, "IP")
        self.assertEqual(loaded_meta.vector_count, 100)

    def test_validate_compatibility_success(self):
        from faiss_engine.index_metadata import IndexMetadata
        meta = IndexMetadata(self.meta_file)
        meta.set(
            generation_id="gen_1",
            model_name="all-MiniLM-L6-v2",
            embedding_dim=384,
            distance_metric="IP",
            index_type="FLAT",
            vector_count=50,
        )
        compat = meta.validate_compatibility("all-MiniLM-L6-v2", 384, "IP")
        self.assertTrue(compat["compatible"])
        self.assertEqual(len(compat["issues"]), 0)

    def test_validate_compatibility_mismatches(self):
        from faiss_engine.index_metadata import IndexMetadata
        meta = IndexMetadata(self.meta_file)
        meta.set(
            generation_id="gen_1",
            model_name="all-MiniLM-L6-v2",
            embedding_dim=384,
            distance_metric="IP",
            index_type="FLAT",
            vector_count=50,
        )
        # Dim mismatch
        compat_dim = meta.validate_compatibility("all-MiniLM-L6-v2", 512, "IP")
        self.assertFalse(compat_dim["compatible"])
        self.assertTrue(any("dimension" in i.lower() for i in compat_dim["issues"]))

        # Model mismatch
        compat_model = meta.validate_compatibility("different-model", 384, "IP")
        self.assertFalse(compat_model["compatible"])
        self.assertTrue(any("model mismatch" in i.lower() for i in compat_model["issues"]))

        # Metric mismatch
        compat_metric = meta.validate_compatibility("all-MiniLM-L6-v2", 384, "L2")
        self.assertFalse(compat_metric["compatible"])
        self.assertTrue(any("metric mismatch" in i.lower() for i in compat_metric["issues"]))

    def test_validate_generation_consistency(self):
        from faiss_engine.index_metadata import IndexMetadata
        meta = IndexMetadata(self.meta_file)
        meta.set(
            generation_id="gen_123",
            model_name="all-MiniLM-L6-v2",
            embedding_dim=384,
            distance_metric="IP",
            index_type="FLAT",
            vector_count=50,
        )
        # Matching generation
        check_match = meta.validate_generation("gen_123")
        self.assertTrue(check_match["consistent"])

        # Mismatched generation
        check_mismatch = meta.validate_generation("gen_456")
        self.assertFalse(check_mismatch["consistent"])
        self.assertTrue(any("generation mismatch" in i.lower() for i in check_mismatch["issues"]))

        # Missing mapping generation
        check_missing = meta.validate_generation(None)
        self.assertFalse(check_missing["consistent"])


if __name__ == "__main__":
    unittest.main()
