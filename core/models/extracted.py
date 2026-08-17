from dataclasses import dataclass, field


@dataclass
class ExtractedBlock:
    text: str
    page: int
    bbox: tuple[float, float, float, float]
    type: str  # pymupdf4llm boxclass: "text", "section-header", "caption", etc.


@dataclass
class ExtractedPage:
    page_number: int
    width: float
    height: float
    blocks: list[ExtractedBlock] = field(default_factory=list)


@dataclass
class ExtractedDocument:
    filename: str
    pages: list[ExtractedPage] = field(default_factory=list)
