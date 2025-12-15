from core.ingest.loader import load_pdf
from core.ingest.extractor import extract_text_blocks
from core.models.text_block import TextBlock
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
SAMPLE_PDF = FIXTURES_DIR / "sample.pdf"

def test_pdf_loads():
    doc = load_pdf(str(SAMPLE_PDF))
    assert doc is not None
    assert len(doc) > 0


def test_extracts_text_blocks():
    doc = load_pdf(str(SAMPLE_PDF))
    blocks = extract_text_blocks(doc)

    assert isinstance(blocks, list)
    assert len(blocks) > 0


def test_blocks_have_required_fields():
    doc = load_pdf(str(SAMPLE_PDF))
    blocks = extract_text_blocks(doc)

    block = blocks[0]
    assert isinstance(block, TextBlock)
    assert isinstance(block.text, str)
    assert block.text.strip() != ""
    assert isinstance(block.page, int)
    assert block.page >= 0
    assert isinstance(block.bbox, tuple)
    assert len(block.bbox) == 4


def test_contains_expected_text():
    doc = load_pdf(str(SAMPLE_PDF))
    blocks = extract_text_blocks(doc)

    full_text = " ".join(b.text for b in blocks).lower()

    assert "attention is all you need" in full_text
