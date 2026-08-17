from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass
class SearchResult:
    chunk_id: int
    document_id: str
    text: str
    heading: str
    score: float
    page: int


class VectorStore(ABC):
    @abstractmethod
    def setup(self) -> None: ...

    @abstractmethod
    def store_chunks(
        self,
        document_id: str,
        texts: list[str],
        embeddings: np.ndarray,
        headings: list[str],
        pages: list[int],
        chunk_indices: list[int],
    ) -> None: ...

    @abstractmethod
    def search(
        self, query_embedding: np.ndarray, top_k: int = 5, score_threshold: float = 0.0
    ) -> list[SearchResult]: ...

    @abstractmethod
    def delete_document(self, document_id: str) -> None: ...

    @abstractmethod
    def close(self) -> None: ...
