from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date

import numpy as np


@dataclass
class SourceBlock:
    text: str
    page: int
    bbox: list[float]
    type: str


@dataclass
class SearchResult:
    chunk_id: int
    document_id: str
    text: str
    heading: str
    score: float
    page: int
    document_date: date | None = None
    source_blocks: list[SourceBlock] = field(default_factory=list)
    # D8: True when this result satisfies the query's date filter (or no
    # date filter was applied). False marks a result backfilled from an
    # unfiltered search to make up a shortfall — see
    # core/api/routes/search.py.
    within_date_range: bool = True


@dataclass
class DocumentInfo:
    document_id: str
    filename: str
    user_id: str
    document_date: date | None = None
    chunk_count: int = 0


class VectorStore(ABC):
    @abstractmethod
    def setup(self) -> None: ...

    @abstractmethod
    def store_chunks(
        self,
        document_id: str,
        user_id: str,
        filename: str,
        texts: list[str],
        embeddings: np.ndarray,
        headings: list[str],
        pages: list[int],
        chunk_indices: list[int],
        document_date: date | None = None,
        source_blocks: list[list[dict]] | None = None,
    ) -> None: ...

    @abstractmethod
    def search(
        self,
        query_embedding: np.ndarray,
        user_id: str,
        top_k: int = 5,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[SearchResult]: ...

    @abstractmethod
    def list_documents(self, user_id: str) -> list[DocumentInfo]: ...

    @abstractmethod
    def update_document_date(
        self, document_id: str, user_id: str, document_date: date | None
    ) -> None: ...

    @abstractmethod
    def delete_document(self, document_id: str, user_id: str) -> None: ...

    @abstractmethod
    def delete_all_for_user(self, user_id: str) -> int: ...

    @abstractmethod
    def close(self) -> None: ...
