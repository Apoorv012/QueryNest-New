from core.ingest.loader import load_pdf
from core.ingest.extractor import extract_text_blocks
from core.ingest.normalizer import merge_spans_to_lines, merge_lines_to_paragraphs
from pathlib import Path


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
SAMPLE_PDF = FIXTURES_DIR / "sample.pdf"


def test_paragraph_merging_reduces_blocks():
    doc = load_pdf(str(SAMPLE_PDF))
    spans = extract_text_blocks(doc)
    lines = merge_spans_to_lines(spans)
    paragraphs = merge_lines_to_paragraphs(lines)

    # merging actually happened
    assert len(paragraphs) < len(spans)

    # no empty paragraphs
    assert all(p.text.strip() for p in paragraphs)

