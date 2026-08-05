import numpy as np
import pytest

from core.embedding.local import LocalEmbedder
from core.embedding.factory import get_embedder


class TestLocalEmbedder:
    """Tests for the fastembed-based local embedder."""

    @pytest.fixture(scope="class")
    def embedder(self):
        """Shared embedder instance (model loads once for all tests)."""
        return LocalEmbedder()

    def test_embed_returns_correct_shape(self, embedder):
        texts = ["Hello world", "This is a test"]
        result = embedder.embed(texts)

        assert isinstance(result, np.ndarray)
        assert result.shape == (2, embedder.dim)
        assert result.dtype == np.float32

    def test_embed_single_text(self, embedder):
        result = embedder.embed(["single text"])
        assert result.shape == (1, embedder.dim)

    def test_embed_empty_list(self, embedder):
        result = embedder.embed([])
        assert result.shape == (0, embedder.dim)

    def test_embed_query_returns_correct_shape(self, embedder):
        result = embedder.embed_query("what is attention?")

        assert isinstance(result, np.ndarray)
        assert result.shape == (1, embedder.dim)
        assert result.dtype == np.float32

    def test_similar_texts_have_high_similarity(self, embedder):
        """Texts with similar meaning should produce similar vectors."""
        v1 = embedder.embed(["The cat sat on the mat"])[0]
        v2 = embedder.embed(["A feline rested on the rug"])[0]
        v3 = embedder.embed(["Quantum physics equations"])[0]

        sim_similar = float(np.dot(v1, v2))
        sim_different = float(np.dot(v1, v3))

        # Related texts should be more similar than unrelated ones
        assert sim_similar > sim_different

    def test_vectors_are_normalized(self, embedder):
        """fastembed should return L2-normalized vectors."""
        result = embedder.embed(["normalize me"])
        norm = float(np.linalg.norm(result[0]))
        assert abs(norm - 1.0) < 0.01  # close to unit length

    def test_dim_property(self, embedder):
        assert embedder.dim == 384  # bge-small-en-v1.5

    def test_batch_consistency(self, embedder):
        """Embedding one at a time should match batched embedding."""
        texts = ["alpha", "beta", "gamma"]
        batched = embedder.embed(texts)
        singles = np.vstack([embedder.embed([t]) for t in texts])

        # Should be very close (floating point tolerance)
        np.testing.assert_allclose(batched, singles, atol=1e-5)


class TestFactory:
    """Tests for the embedder factory."""

    def test_get_local_embedder(self):
        embedder = get_embedder(use_cloud=False)
        assert isinstance(embedder, LocalEmbedder)

    def test_cloud_raises_not_implemented(self):
        with pytest.raises(NotImplementedError):
            get_embedder(use_cloud=True)
