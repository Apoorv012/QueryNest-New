import numpy as np
from fastembed import TextEmbedding

from .base import BaseEmbedder


class FastEmbedEmbedder(BaseEmbedder):
    """Embedding model using fastembed (ONNX Runtime)."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        """
        Initialize the fastembed embedder.

        Args:
            model_name: Name of the fastembed model to use
        """
        self._model_name = model_name
        self._model = TextEmbedding(model_name=model_name)
        self._embedding_dim = self._model.embedding_size

    def embed(self, texts: list[str], batch_size: int = 256) -> np.ndarray:
        """
        Embed a list of texts into dense vectors.

        Args:
            texts: List of strings to embed
            batch_size: Number of texts to process per batch

        Returns:
            numpy array of shape (n_texts, embedding_dim)
        """
        embeddings = list(self._model.embed(texts, batch_size=batch_size))
        return np.array(embeddings)

    def embed_query(self, query: str) -> np.ndarray:
        """
        Embed a single query string.

        Args:
            query: Query string to embed

        Returns:
            numpy array of shape (embedding_dim,)
        """
        embedding = next(iter(self._model.embed([query])))
        return embedding

    @property
    def embedding_dim(self) -> int:
        """Return the dimensionality of the embedding vectors."""
        return self._embedding_dim
