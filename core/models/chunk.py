from dataclasses import dataclass, field

from core.models.extracted import ExtractedBlock


@dataclass
class Chunk:
    text: str
    source_blocks: list[ExtractedBlock] = field(default_factory=list)
    heading: str = ""
    chunk_index: int = 0
