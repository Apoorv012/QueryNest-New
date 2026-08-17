from dataclasses import dataclass, field
from typing import List, Tuple
from core.models.extracted import ExtractedBlock


@dataclass
class Chunk:
    text: str
    source_blocks: List[ExtractedBlock] = field(default_factory=list)
    heading: str = ""
    chunk_index: int = 0
