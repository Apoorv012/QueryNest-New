from abc import ABC, abstractmethod

import numpy as np


class BaseEmbedder(ABC):
    """Base class for text embedding models."""

    @abstractmethod
    def embed(self, texts: list[str], batch_size: int = 256) -> np.ndarray:
        """
        Embed a list of texts into dense vectors.

        Args:
            texts: List of strings to embed
            batch_size: Number of texts to process per batch

        Returns:
            numpy array of shape (n_texts, embedding_dim)
        """
        ...

    @abstractmethod
    def embed_query(self, query: str) -> np.ndarray:
        """
        Embed a single query string.

        Args:
            query: Query string to embed

        Returns:
            numpy array of shape (embedding_dim,)
        """
        ...

    @property
    @abstractmethod
    def embedding_dim(self) -> int:
        """Return the dimensionality of the embedding vectors."""
        ...
