from typing import List, Optional
import numpy as np
from core.embedding.base import BaseEmbedder

# Default model: small, fast, good quality for semantic search
DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_DIM = 384


class LocalEmbedder(BaseEmbedder):
    """
    Local embedding using fastembed (ONNX runtime).

    - ~50MB model download on first use (cached automatically).
    - ~50ms per chunk on CPU.
    - Uses BAAI/bge-small-en-v1.5 by default (384-dim).
    - Vectors are L2-normalized by fastembed.

    BGE models use special prefixes:
    - Passages get no prefix (fastembed handles this).
    - Queries should use embed_query() which adds "query: " internally.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        cache_dir: Optional[str] = None,
    ):
        self._model_name = model_name
        self._cache_dir = cache_dir
        self._model = None  # lazy init
        self._dim: Optional[int] = None

    def _ensure_model(self):
        """Lazy-load the model on first use."""
        if self._model is not None:
            return

        from fastembed import TextEmbedding

        kwargs = {"model_name": self._model_name}
        if self._cache_dir:
            kwargs["cache_dir"] = self._cache_dir

        self._model = TextEmbedding(**kwargs)

        # Determine embedding dimension from a probe
        probe = list(self._model.embed(["dimension probe"]))[0]
        self._dim = len(probe)

    def embed(self, texts: List[str]) -> np.ndarray:
        """
        Embed a list of passage/document texts.

        Args:
            texts: List of strings (chunks, paragraphs, etc.)

        Returns:
            np.ndarray of shape (len(texts), dim), dtype float32.
        """
        if not texts:
            return np.empty((0, self.dim), dtype=np.float32)

        self._ensure_model()
        embeddings = list(self._model.passage_embed(texts))
        return np.array(embeddings, dtype=np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        """
        Embed a single search query.

        Uses the "query: " prefix for BGE models, which improves
        retrieval quality.

        Args:
            query: The search query string.

        Returns:
            np.ndarray of shape (1, dim), dtype float32.
        """
        self._ensure_model()
        embeddings = list(self._model.query_embed(query))
        return np.array(embeddings, dtype=np.float32)

    @property
    def dim(self) -> int:
        """Dimensionality of the embedding vectors."""
        if self._dim is None:
            # If dim unknown, we need to load the model
            if self._model_name == DEFAULT_MODEL:
                return DEFAULT_DIM
            self._ensure_model()
        return self._dim
