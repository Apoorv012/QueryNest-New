from core.models.extracted import ExtractedBlock, ExtractedPage, ExtractedDocument


def test_extracted_block_construction():
    b = ExtractedBlock(text="Hello", page=0, bbox=(1, 2, 3, 4), type="text")
    assert b.text == "Hello"
    assert b.page == 0
    assert b.type == "text"


def test_extracted_page_construction():
    p = ExtractedPage(page_number=1, width=612, height=792)
    assert p.page_number == 1
    assert p.blocks == []


def test_extracted_document_construction():
    p = ExtractedPage(page_number=1, width=612, height=792)
    doc = ExtractedDocument(filename="test.pdf", pages=[p])
    assert doc.filename == "test.pdf"
    assert len(doc.pages) == 1
