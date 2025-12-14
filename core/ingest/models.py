from dataclasses import dataclass
from typing import Tuple

@dataclass
class TextBlock:
    text: str
    page: int
    bbox: Tuple[float, float, float, float] # x0, y0, x1, y1
    page_height: float
