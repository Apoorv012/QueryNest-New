import os
import tempfile

import numpy as np
import pytest

from core.index.faiss_index import FaissIndex, SearchHit


class TestFaissIndex:
    """Tests for the FAISS vector index."""

    DIM = 8  # small dim for fast tests

    def _random_vectors(self, n: int) -> np.ndarray:
        """Generate random L2-normalized vectors."""
        vecs = np.random.randn(n, self.DIM).astype(np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        return vecs / norms

    def test_create_empty_index(self):
        idx = FaissIndex(dim=self.DIM)
        assert idx.size == 0
        assert idx.dim == self.DIM

    def test_add_vectors(self):
        idx = FaissIndex(dim=self.DIM)
        vecs = self._random_vectors(5)
        idx.add(vecs, document_id="doc1")
        assert idx.size == 5

    def test_add_multiple_documents(self):
        idx = FaissIndex(dim=self.DIM)
        idx.add(self._random_vectors(3), document_id="doc1")
        idx.add(self._random_vectors(4), document_id="doc2")
        assert idx.size == 7

    def test_search_returns_results(self):
        idx = FaissIndex(dim=self.DIM)
        vecs = self._random_vectors(10)
        idx.add(vecs, document_id="doc1")

        # Search with one of the indexed vectors → should find itself
        hits = idx.search(vecs[0:1], top_k=3)

        assert len(hits) == 3
        assert isinstance(hits[0], SearchHit)
        # The query vector itself should be the top hit (score ≈ 1.0)
        assert hits[0].score > 0.99
        assert hits[0].document_id == "doc1"
        assert hits[0].chunk_index == 0

    def test_search_empty_index(self):
        idx = FaissIndex(dim=self.DIM)
        query = self._random_vectors(1)
        hits = idx.search(query, top_k=5)
        assert hits == []

    def test_search_top_k_larger_than_index(self):
        idx = FaissIndex(dim=self.DIM)
        idx.add(self._random_vectors(3), document_id="doc1")
        query = self._random_vectors(1)
        hits = idx.search(query, top_k=100)
        assert len(hits) == 3  # clamped to index size

    def test_search_preserves_document_id(self):
        idx = FaissIndex(dim=self.DIM)

        # Two documents with different vectors
        v1 = self._random_vectors(2)
        v2 = self._random_vectors(2)
        idx.add(v1, document_id="alpha")
        idx.add(v2, document_id="beta")

        # Search with v1[0] → should match "alpha"
        hits = idx.search(v1[0:1], top_k=1)
        assert hits[0].document_id == "alpha"

    def test_chunk_index_offset(self):
        idx = FaissIndex(dim=self.DIM)
        vecs = self._random_vectors(3)
        idx.add(vecs, document_id="doc1", start_chunk_index=10)

        hits = idx.search(vecs[2:3], top_k=1)
        assert hits[0].chunk_index == 12  # 10 + 2

    def test_add_wrong_dimension_raises(self):
        idx = FaissIndex(dim=self.DIM)
        wrong_vecs = np.random.randn(3, self.DIM + 1).astype(np.float32)
        with pytest.raises(ValueError, match="Expected vectors"):
            idx.add(wrong_vecs, document_id="doc1")

    def test_remove_document(self):
        idx = FaissIndex(dim=self.DIM)
        idx.add(self._random_vectors(3), document_id="keep")
        idx.add(self._random_vectors(5), document_id="remove")
        assert idx.size == 8

        removed = idx.remove_document("remove")
        assert removed == 5
        assert idx.size == 3

        # All remaining entries should be "keep"
        hits = idx.search(self._random_vectors(1), top_k=10)
        for h in hits:
            assert h.document_id == "keep"

    def test_remove_nonexistent_document(self):
        idx = FaissIndex(dim=self.DIM)
        idx.add(self._random_vectors(3), document_id="doc1")
        removed = idx.remove_document("nonexistent")
        assert removed == 0
        assert idx.size == 3

    def test_save_and_load(self, tmp_path):
        # Create and populate index
        idx = FaissIndex(dim=self.DIM)
        vecs = self._random_vectors(5)
        idx.add(vecs, document_id="doc1")
        idx.add(self._random_vectors(3), document_id="doc2")

        save_dir = str(tmp_path / "index_test")
        idx.save(save_dir)

        # Verify files exist
        assert os.path.exists(os.path.join(save_dir, "index.faiss"))
        assert os.path.exists(os.path.join(save_dir, "index_meta.json"))

        # Load and verify
        loaded = FaissIndex.load(save_dir)
        assert loaded.dim == self.DIM
        assert loaded.size == 8

        # Search should still work
        hits = loaded.search(vecs[0:1], top_k=1)
        assert hits[0].document_id == "doc1"
        assert hits[0].score > 0.99

    def test_load_missing_directory_raises(self):
        with pytest.raises(FileNotFoundError):
            FaissIndex.load("/nonexistent/path")

    def test_results_sorted_by_score(self):
        idx = FaissIndex(dim=self.DIM)
        idx.add(self._random_vectors(20), document_id="doc1")
        query = self._random_vectors(1)
        hits = idx.search(query, top_k=10)

        scores = [h.score for h in hits]
        assert scores == sorted(scores, reverse=True)
