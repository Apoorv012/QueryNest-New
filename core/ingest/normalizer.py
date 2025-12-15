from typing import List
from .models import TextBlock
import re

LINE_Y_TOLERANCE = 2.5  # tighter than paragraph gap
PARA_GAP = 10.0


def merge_spans_to_lines(blocks: List[TextBlock]) -> List[TextBlock]:
    lines: List[TextBlock] = []

    # sort top-to-bottom, then left-to-right
    blocks = sorted(blocks, key=lambda b: (b.page, b.bbox[1], b.bbox[0]))

    current = None

    for b in blocks:
        x0, y0, x1, y1 = b.bbox

        if current is None:
            current = b
            continue

        same_page = b.page == current.page
        same_line = abs(y0 - current.bbox[1]) < LINE_Y_TOLERANCE

        if same_page and same_line:
            # horizontal merge (CRITICAL)
            current = TextBlock(
                text=" ".join((current.text, b.text)),
                page=current.page,
                bbox=(
                    min(current.bbox[0], x0),
                    min(current.bbox[1], y0),
                    max(current.bbox[2], x1),
                    max(current.bbox[3], y1),
                ),
                page_height=current.page_height,
            )
        else:
            lines.append(current)
            current = b

    if current:
        lines.append(current)

    return lines


def merge_lines_to_paragraphs(blocks: List[TextBlock]) -> List[TextBlock]:
    paragraphs: List[TextBlock] = []

    current_text = []
    current_bbox: List[float] = [0.0, 0.0, 0.0, 0.0]
    current_page: int = -1
    last_y: float = 0.0

    for block in blocks:
        x0, y0, x1, y1 = block.bbox

        if current_page == -1:
            # start first paragraph
            current_page = block.page
            current_text = [block.text]
            current_bbox = [x0, y0, x1, y1]
            last_y = y1
            continue

        same_page = block.page == current_page
        close_vertically = abs(y0 - last_y) < PARA_GAP

        if same_page and close_vertically:
            # continue paragraph
            current_text.append(block.text)
            current_bbox[0] = min(current_bbox[0], x0)
            current_bbox[1] = min(current_bbox[1], y0)
            current_bbox[2] = max(current_bbox[2], x1)
            current_bbox[3] = max(current_bbox[3], y1)
        else:
            # flush previous paragraph
            paragraphs.append(
                TextBlock(
                    text=" ".join(current_text),
                    page=current_page,
                    bbox=(current_bbox[0], current_bbox[1], current_bbox[2], current_bbox[3]),
                    page_height=block.page_height
                )
            )
            # start new paragraph
            current_page = block.page
            current_text = [block.text]
            current_bbox = [x0, y0, x1, y1]

        last_y = y1

    # flush last paragraph
    if current_text:
        paragraphs.append(
            TextBlock(
                text=" ".join(current_text),
                page=current_page,
                bbox=(current_bbox[0], current_bbox[1], current_bbox[2], current_bbox[3]),
                page_height=block.page_height
            )
        )

    return paragraphs


