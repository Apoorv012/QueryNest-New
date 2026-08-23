from core.chunking.chunker import DROP_BELOW_TOKENS, _chunk_blocks, chunk_document
from core.chunking.tokenizer import estimate_tokens
from core.models.extracted import ExtractedBlock, ExtractedDocument, ExtractedPage


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


class TestDropUnusableChunks:
    """Consecutive section-headers emit a chunk whose entire content is the
    first heading ("4 Results", "E Additional Details"). At 2-3 tokens these
    embed to a vague near-centroid vector that sits at middling distance from
    every query, so they surface as plausible noise — measured at ranks 3 and 6
    for "job descriptions", ahead of three real job descriptions."""

    @staticmethod
    def _block(text, block_type="text"):
        return ExtractedBlock(text=text, page=0, bbox=(0, 0, 1, 1), type=block_type)

    @classmethod
    def _doc(cls, blocks):
        return ExtractedDocument(
            filename="x",
            pages=[ExtractedPage(page_number=0, width=1, height=1, blocks=blocks)],
        )

    BODY = " ".join(["word"] * 200)

    def test_heading_only_chunk_is_dropped(self):
        doc = self._doc([
            self._block("4 Results", "section-header"),
            self._block("E Additional Details", "section-header"),
            self._block(self.BODY),
        ])
        chunks = chunk_document(doc)
        assert all(estimate_tokens(c.text) >= DROP_BELOW_TOKENS for c in chunks)
        assert not any(c.text.strip() == "4 Results" for c in chunks)

    def test_real_content_is_never_dropped(self):
        doc = self._doc([
            self._block("H1", "section-header"), self._block(self.BODY),
            self._block("H2", "section-header"), self._block(self.BODY),
        ])
        assert len(chunk_document(doc)) >= 2

    def test_an_entirely_tiny_document_is_still_indexed(self):
        # Dropping must never remove a document from the corpus outright — a
        # one-line receipt should still be findable.
        chunks = chunk_document(self._doc([self._block("paid in full")]))
        assert len(chunks) == 1
        assert "paid in full" in chunks[0].text

    def test_chunk_indices_stay_contiguous_after_dropping(self):
        doc = self._doc([
            self._block("A", "section-header"),
            self._block("B", "section-header"), self._block(self.BODY),
            self._block("C", "section-header"), self._block(self.BODY),
        ])
        chunks = chunk_document(doc)
        assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
