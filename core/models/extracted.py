from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class ExtractedBlock:
    text: str
    page: int
    bbox: Tuple[float, float, float, float]
    type: str  # pymupdf4llm boxclass: "text", "section-header", "caption", etc.


@dataclass
class ExtractedPage:
    page_number: int
    width: float
    height: float
    blocks: List[ExtractedBlock] = field(default_factory=list)


@dataclass
class ExtractedDocument:
    filename: str
    pages: List[ExtractedPage] = field(default_factory=list)
