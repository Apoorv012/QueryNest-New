from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date

import numpy as np

# How a result relates to the query's date filter, in descending confidence.
# Ordering matters: tiers are served in this sequence (D12).
DATE_MATCH_IN_RANGE = "in_range"        # dated, and inside the requested range
DATE_MATCH_UNDATED = "undated"          # no date known - might match
DATE_MATCH_OUT_OF_RANGE = "out_of_range"  # dated, and outside the range
DATE_MATCH_UNFILTERED = "unfiltered"    # no date filter was applied at all


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
    filename: str = ""
    document_date: date | None = None
    source_blocks: list[SourceBlock] = field(default_factory=list)
    # D8/D12: how this result relates to the query's date filter. Three
    # states, not two: an undated document *might* match the requested range
    # (we cannot tell), whereas a document dated outside it is a known
    # non-match. Collapsing those into one boolean claimed a confidence the
    # system does not have. See core/api/routes/search.py.
    date_match: str = DATE_MATCH_UNFILTERED


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
        content_hash: str | None = None,
        page_count: int | None = None,
    ) -> None: ...

    @abstractmethod
    def find_by_content_hash(self, user_id: str, content_hash: str) -> str | None:
        """Return an existing document_id with this content hash, or None.

        Enables skipping re-ingest of a byte-identical file: extraction is
        ~77% of ingest cost at roughly 1790 ms/page, so this removes work
        rather than rearranging it.
        """
        ...

    @abstractmethod
    def search(
        self,
        query_embedding: np.ndarray,
        user_id: str,
        top_k: int = 5,
        date_from: date | None = None,
        date_to: date | None = None,
        date_mode: str | None = None,
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
