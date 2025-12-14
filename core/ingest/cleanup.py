from typing import List
from collections import defaultdict
from .models import TextBlock
import re

TOP_RATIO = 0.1       # top 10%
BOTTOM_RATIO = 0.9    # bottom 10%
MIN_PAGE_REPEATS = 3        # appears on ≥ 3 pages

PAGE_NUMBER_RE = re.compile(r"^(page\s*)?\d+$", re.IGNORECASE)


def is_page_number(text: str) -> bool:
    return bool(PAGE_NUMBER_RE.match(text.strip()))


def remove_headers_and_footers(
    paragraphs: List[TextBlock]
) -> List[TextBlock]:

    text_pages = defaultdict(set)

    # Track where each text appears
    for p in paragraphs:
        text = p.text.strip().lower()
        if text:
            text_pages[text].add(p.page)

    cleaned = []

    for p in paragraphs:
        text_key = p.text.strip().lower()
        repeats = len(text_pages[text_key])
        page_height = p.page_height

        y0 = p.bbox[1]

        is_top = (y0 / page_height) < TOP_RATIO
        is_bottom = (y0 / page_height) > BOTTOM_RATIO

        is_repeated = repeats >= MIN_PAGE_REPEATS

        if is_repeated and (is_top or is_bottom):
            continue  # drop header/footer
        
        if (is_top or is_bottom) and is_page_number(p.text):
            continue

        cleaned.append(p)

    return cleaned

