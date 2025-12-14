from core.ingest.loader import load_pdf
from core.ingest.extractor import extract_text_blocks
from core.ingest.normalizer import merge_spans_to_paragraphs
from core.ingest.cleanup import remove_headers_and_footers
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
SAMPLE_PDF = FIXTURES_DIR / "sample.pdf"

TOP_RATIO = 0.1       # top 10%
BOTTOM_RATIO = 0.9    # bottom 10%


def test_headers_removed():
    doc = load_pdf(str(SAMPLE_PDF))
    spans = extract_text_blocks(doc)
    paragraphs = merge_spans_to_paragraphs(spans)
    cleaned = remove_headers_and_footers(paragraphs)

    texts = [p.text.lower() for p in cleaned]

    # Running title should not dominate
    assert texts.count("attention is all you need") < 2


def test_page_numbers_removed_by_position():
    doc = load_pdf(str(SAMPLE_PDF))
    spans = extract_text_blocks(doc)
    paragraphs = merge_spans_to_paragraphs(spans)
    cleaned = remove_headers_and_footers(paragraphs)

    for p in cleaned:
        text = p.text.strip()
        y0 = p.bbox[1]
        page_height = p.page_height

        is_numeric = text.isdigit()
        is_top = (y0 / page_height) < TOP_RATIO
        is_bottom = (y0 / page_height) > BOTTOM_RATIO

        # numeric junk should not survive at page edges
        assert not (is_numeric and (is_top or is_bottom))
