from abc import ABC, abstractmethod
from typing import List
import numpy as np


class BaseEmbedder(ABC):
    """
    Abstract base class for all embedding backends.

    Implementations must:
    - Return L2-normalized vectors (unit length) so that
      dot-product == cosine similarity.
    - Accept batches of text and return a 2D numpy array.
    """

    @abstractmethod
    def embed(self, texts: List[str]) -> np.ndarray:
        """
        Embed a list of texts into dense vectors.

        Args:
            texts: List of strings to embed.

        Returns:
            np.ndarray of shape (len(texts), self.dim), dtype float32.
            Vectors are L2-normalized.
        """
        ...

    @abstractmethod
    def embed_query(self, query: str) -> np.ndarray:
        """
        Embed a single search query.

        Some models (e.g., BGE) use different prefixes for queries
        vs. passages. This method handles that distinction.

        Args:
            query: The search query string.

        Returns:
            np.ndarray of shape (1, self.dim), dtype float32.
        """
        ...

    @property
    @abstractmethod
    def dim(self) -> int:
        """Dimensionality of the embedding vectors."""
        ...
