from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class Chunk:
    text: str
    pages: List[int]
    bboxes: List[Tuple[float, float, float, float]]
