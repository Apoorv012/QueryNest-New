def test_extract_returns_populated_document(extracted_doc):
    total_blocks = sum(len(p.blocks) for p in extracted_doc.pages)
    assert total_blocks > 0


def test_blocks_are_grouped_by_page(extracted_doc):
    for page in extracted_doc.pages:
        for block in page.blocks:
            assert block.page == page.page_number - 1
