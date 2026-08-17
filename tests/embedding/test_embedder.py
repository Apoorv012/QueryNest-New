import numpy as np
import pytest

from core.embedding import BaseEmbedder, FastEmbedEmbedder


class TestBaseEmbedder:
    def test_is_abstract(self):
        with pytest.raises(TypeError):
            BaseEmbedder()


class TestFastEmbedEmbedder:
    @pytest.fixture(scope="module")
    def embedder(self):
        return FastEmbedEmbedder()

    def test_embedding_dim(self, embedder):
        assert embedder.embedding_dim == 384

    def test_embed_single_text(self, embedder):
        embeddings = embedder.embed(["hello world"])
        assert embeddings.shape == (1, 384)
        assert embeddings.dtype == np.float32

    def test_embed_multiple_texts(self, embedder):
        texts = ["hello world", "test document", "query about AI"]
        embeddings = embedder.embed(texts)
        assert embeddings.shape == (3, 384)

    def test_embed_query(self, embedder):
        embedding = embedder.embed_query("test query")
        assert embedding.shape == (384,)
        assert embedding.dtype == np.float32

    def test_embeddings_are_normalized(self, embedder):
        embeddings = embedder.embed(["test text"])
        norms = np.linalg.norm(embeddings, axis=1)
        np.testing.assert_allclose(norms, 1.0, atol=1e-5)

    def test_similar_texts_are_closer(self, embedder):
        texts = [
            "machine learning is a subset of AI",
            "deep learning is a type of machine learning",
            "the weather is nice today",
        ]
        embeddings = embedder.embed(texts)

        # Compute cosine similarity (dot product for normalized vectors)
        similarities = embeddings @ embeddings.T

        # ML texts should be more similar to each other than to weather
        assert similarities[0, 1] > similarities[0, 2]
        assert similarities[0, 1] > similarities[1, 2]
