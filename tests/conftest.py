import pytest

from core.ingest.extractor import extract

SAMPLE_PDF = "tests/fixtures/sample.pdf"


@pytest.fixture(scope="session")
def extracted_doc():
    return extract(SAMPLE_PDF)
