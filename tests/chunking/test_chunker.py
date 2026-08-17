from core.chunking.chunker import _chunk_blocks
from core.models.extracted import ExtractedBlock


def _block(text, btype="text"):
    return ExtractedBlock(text=text, page=0, bbox=(0, 0, 100, 50), type=btype)


def _header(text):
    return _block(text, btype="section-header")


def _long_text(n_words=300):
    return " ".join(["word"] * n_words)


def test_single_text_blocks_produce_one_chunk():
    blocks = [_block("Hello world"), _block("Another paragraph")]
    chunks = _chunk_blocks(blocks)
    assert len(chunks) == 1
    assert chunks[0].heading == ""


def test_section_header_creates_new_chunk():
    blocks = [
        _block("Some intro text here"),
        _header("1 Introduction"),
        _block("Introduction paragraph one"),
        _block("Introduction paragraph two"),
    ]
    chunks = _chunk_blocks(blocks)
    assert len(chunks) == 2
    assert chunks[0].heading == ""
    assert chunks[1].heading == "1 Introduction"


def test_heading_heading_groups_content():
    blocks = [
        _header("Abstract"),
        _block("This is the abstract."),
        _header("1 Introduction"),
        _block("Intro paragraph."),
    ]
    chunks = _chunk_blocks(blocks)
    assert len(chunks) == 2
    assert "Abstract" in chunks[0].heading
    assert "Introduction" in chunks[1].heading
    assert "This is the abstract." in chunks[0].text


def test_token_overflow_flushes_chunk():
    blocks = [
        _header("Big Section"),
        _block(_long_text(200)),
        _block(_long_text(200)),
    ]
    chunks = _chunk_blocks(blocks)
    assert len(chunks) >= 2
    assert all(c.heading == "Big Section" for c in chunks)


def test_small_section_stays_together():
    blocks = [
        _header("Short Section"),
        _block("Short paragraph."),
        _block("Another short paragraph."),
    ]
    chunks = _chunk_blocks(blocks)
    assert len(chunks) == 1


def test_chunk_indices_are_sequential():
    blocks = [
        _header("A"), _block("content a"),
        _header("B"), _block("content b"),
        _header("C"), _block("content c"),
    ]
    chunks = _chunk_blocks(blocks)
    indices = [c.chunk_index for c in chunks]
    assert indices == list(range(len(chunks)))


def test_source_blocks_preserved():
    b1 = _block("First paragraph text")
    b2 = _block("Second paragraph text")
    blocks = [_header("Sec"), b1, b2]
    chunks = _chunk_blocks(blocks)
    assert len(chunks[0].source_blocks) == 3
    assert chunks[0].source_blocks[1] is b1
    assert chunks[0].source_blocks[2] is b2


def test_empty_input():
    chunks = _chunk_blocks([])
    assert chunks == []


def test_only_headers_no_crash():
    blocks = [_header("A"), _header("B"), _header("C")]
    chunks = _chunk_blocks(blocks)
    assert len(chunks) == 3


def test_real_pdf_chunking(extracted_doc):
    from core.chunking.chunker import chunk_document

    chunks = chunk_document(extracted_doc)
    assert len(chunks) > 5
    assert len(chunks) < 100
    assert all(c.text.strip() != "" for c in chunks)
    assert all(c.heading != "" for c in chunks[1:])
    assert chunks[0].chunk_index == 0
