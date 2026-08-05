import os
import json
from typing import List
from dataclasses import dataclass

import numpy as np
import faiss


@dataclass
class IndexEntry:
    """Maps a FAISS vector position to its source document and chunk."""
    document_id: str
    chunk_index: int


@dataclass
class SearchHit:
    """A single search result from the FAISS index."""
    document_id: str
    chunk_index: int
    score: float  # cosine similarity (0.0 to 1.0 for normalized vectors)


class FaissIndex:
    """
    FAISS-based vector index for semantic search.

    Uses IndexFlatIP (inner product) which equals cosine similarity
    when vectors are L2-normalized (fastembed does this automatically).

    Features:
    - Add vectors with document/chunk metadata.
    - Search for top-K nearest neighbors.
    - Save/load to disk (index + metadata sidecar).
    - Incremental: add new documents without rebuilding.
    """

    def __init__(self, dim: int):
        """
        Create a new empty index.

        Args:
            dim: Dimensionality of the vectors (e.g., 384 for bge-small-en).
        """
        self._dim = dim
        self._index = faiss.IndexFlatIP(dim)
        self._entries: List[IndexEntry] = []

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def size(self) -> int:
        """Number of vectors currently in the index."""
        return self._index.ntotal

    def add(
        self,
        vectors: np.ndarray,
        document_id: str,
        start_chunk_index: int = 0,
    ) -> None:
        """
        Add vectors for a single document.

        Args:
            vectors: np.ndarray of shape (n, dim), dtype float32.
                     Must be L2-normalized.
            document_id: ID of the source document.
            start_chunk_index: Index of the first chunk (default 0).
        """
        if vectors.ndim != 2 or vectors.shape[1] != self._dim:
            raise ValueError(
                f"Expected vectors of shape (n, {self._dim}), "
                f"got {vectors.shape}"
            )

        vectors = np.ascontiguousarray(vectors, dtype=np.float32)
        self._index.add(vectors)

        for i in range(vectors.shape[0]):
            self._entries.append(
                IndexEntry(
                    document_id=document_id,
                    chunk_index=start_chunk_index + i,
                )
            )

    def search(self, query_vector: np.ndarray, top_k: int = 10) -> List[SearchHit]:
        """
        Search for the top-K most similar vectors.

        Args:
            query_vector: np.ndarray of shape (1, dim), dtype float32.
                          Must be L2-normalized.
            top_k: Number of results to return.

        Returns:
            List of SearchHit, sorted by score (descending).
        """
        if self.size == 0:
            return []

        # Clamp top_k to the number of vectors in the index
        effective_k = min(top_k, self.size)

        query_vector = np.ascontiguousarray(
            query_vector.reshape(1, -1), dtype=np.float32
        )
        scores, indices = self._index.search(query_vector, effective_k)

        hits = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue  # FAISS returns -1 for missing results
            entry = self._entries[idx]
            hits.append(
                SearchHit(
                    document_id=entry.document_id,
                    chunk_index=entry.chunk_index,
                    score=float(score),
                )
            )

        return hits

    def remove_document(self, document_id: str) -> int:
        """
        Remove all vectors belonging to a document.

        Since FAISS IndexFlat doesn't support deletion natively,
        this rebuilds the index without the removed vectors.

        Args:
            document_id: ID of the document to remove.

        Returns:
            Number of vectors removed.
        """
        if self.size == 0:
            return 0

        # Find indices to keep
        keep_mask = [
            e.document_id != document_id for e in self._entries
        ]

        removed_count = keep_mask.count(False)
        if removed_count == 0:
            return 0

        # Reconstruct all vectors
        all_vectors = faiss.rev_swig_ptr(
            self._index.get_xb(), self.size * self._dim
        ).reshape(self.size, self._dim).copy()

        # Filter
        keep_indices = [i for i, keep in enumerate(keep_mask) if keep]
        kept_vectors = all_vectors[keep_indices]
        kept_entries = [self._entries[i] for i in keep_indices]

        # Rebuild
        self._index = faiss.IndexFlatIP(self._dim)
        self._entries = kept_entries

        if len(kept_vectors) > 0:
            self._index.add(np.ascontiguousarray(kept_vectors, dtype=np.float32))

        return removed_count

    def save(self, directory: str) -> None:
        """
        Save the index and metadata to a directory.

        Creates two files:
        - index.faiss: The FAISS binary index.
        - index_meta.json: The document/chunk mapping.

        Args:
            directory: Directory to save to (created if missing).
        """
        os.makedirs(directory, exist_ok=True)

        index_path = os.path.join(directory, "index.faiss")
        meta_path = os.path.join(directory, "index_meta.json")

        faiss.write_index(self._index, index_path)

        meta = {
            "dim": self._dim,
            "entries": [
                {"document_id": e.document_id, "chunk_index": e.chunk_index}
                for e in self._entries
            ],
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

    @classmethod
    def load(cls, directory: str) -> "FaissIndex":
        """
        Load a previously saved index.

        Args:
            directory: Directory containing index.faiss and index_meta.json.

        Returns:
            A FaissIndex instance with the loaded data.

        Raises:
            FileNotFoundError: If the index files don't exist.
        """
        index_path = os.path.join(directory, "index.faiss")
        meta_path = os.path.join(directory, "index_meta.json")

        if not os.path.exists(index_path):
            raise FileNotFoundError(f"FAISS index not found: {index_path}")
        if not os.path.exists(meta_path):
            raise FileNotFoundError(f"Index metadata not found: {meta_path}")

        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        instance = cls.__new__(cls)
        instance._dim = meta["dim"]
        instance._index = faiss.read_index(index_path)
        instance._entries = [
            IndexEntry(
                document_id=e["document_id"],
                chunk_index=e["chunk_index"],
            )
            for e in meta["entries"]
        ]

        return instance
