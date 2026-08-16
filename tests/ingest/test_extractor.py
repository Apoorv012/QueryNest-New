from core.models.extracted import ExtractedDocument, ExtractedPage, ExtractedBlock


def test_returns_extracted_document(extracted_doc):
    assert isinstance(extracted_doc, ExtractedDocument)
    assert extracted_doc.filename != ""
    assert len(extracted_doc.pages) > 0


def test_pages_have_structure(extracted_doc):
    for page in extracted_doc.pages:
        assert isinstance(page, ExtractedPage)
        assert page.page_number >= 1
        assert page.width > 0
        assert page.height > 0


def test_blocks_have_valid_fields(extracted_doc):
    for page in extracted_doc.pages:
        for block in page.blocks:
            assert isinstance(block, ExtractedBlock)
            assert block.text.strip() != ""
            assert block.page >= 0
            assert isinstance(block.bbox, tuple)
            assert len(block.bbox) == 4
            assert block.type != ""


def test_bbox_within_page_bounds(extracted_doc):
    for page in extracted_doc.pages:
        for block in page.blocks:
            x0, y0, x1, y1 = block.bbox
            assert x0 >= 0
            assert y0 >= 0
            assert x1 <= page.width * 2
            assert y1 <= page.height


def test_contains_expected_text(extracted_doc):
    all_text = " ".join(
        b.text for page in extracted_doc.pages for b in page.blocks
    ).lower()
    assert "attention is all you need" in all_text


def test_no_headers_footers(extracted_doc):
    all_text = " ".join(
        b.text for page in extracted_doc.pages for b in page.blocks
    ).lower()
    count = all_text.count("attention is all you need")
    assert count <= 1


def test_section_headers_detected(extracted_doc):
    headers = [
        b.text for page in extracted_doc.pages for b in page.blocks
        if b.type == "section-header"
    ]
    assert len(headers) > 0
    assert any("abstract" in h.lower() for h in headers)
