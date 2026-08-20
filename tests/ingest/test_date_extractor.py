from datetime import date

from core.ingest.date_extractor import (
    extract_date,
    extract_date_from_filename,
    extract_date_from_metadata,
    extract_date_from_text,
)


class TestExtractDateFromFilename:
    def test_year_in_filename(self):
        d = extract_date_from_filename("CS_Exam_2024.pdf")
        assert d == date(2024, 1, 1)

    def test_year_at_start(self):
        d = extract_date_from_filename("2023_annual_report.pdf")
        assert d == date(2023, 1, 1)

    def test_no_year(self):
        d = extract_date_from_filename("report.pdf")
        assert d is None

    def test_year_in_middle(self):
        d = extract_date_from_filename("exam_paper_2022_v2.pdf")
        assert d == date(2022, 1, 1)


class TestExtractDateFromMetadata:
    def test_creation_date(self):
        d = extract_date_from_metadata({"creationDate": "D:20240315120000"})
        assert d == date(2024, 3, 15)

    def test_mod_date(self):
        d = extract_date_from_metadata({"modDate": "D:20231201"})
        assert d == date(2023, 12, 1)

    def test_year_only(self):
        d = extract_date_from_metadata({"creationDate": "2022"})
        assert d == date(2022, 1, 1)

    def test_no_date(self):
        d = extract_date_from_metadata({})
        assert d is None


class TestExtractDateFromText:
    def test_published_keyword(self):
        d = extract_date_from_text("Published in 2024 by IEEE")
        assert d == date(2024, 1, 1)

    def test_month_year(self):
        d = extract_date_from_text("March 2023")
        assert d == date(2023, 1, 1)

    def test_no_date(self):
        d = extract_date_from_text("This is just some text")
        assert d is None


class TestExtractDate:
    def test_filename_priority(self):
        d, src = extract_date("Exam_2024.pdf")
        assert d == date(2024, 1, 1)
        assert src == "filename"

    def test_metadata_fallback(self):
        d, src = extract_date(
            "report.pdf",
            pdf_metadata={"creationDate": "D:20230615"},
        )
        assert d == date(2023, 6, 15)
        assert src == "metadata"

    def test_content_fallback(self):
        d, src = extract_date(
            "paper.pdf",
            first_page_text="Published in 2022 by ACM",
        )
        assert d == date(2022, 1, 1)
        assert src == "content"

    def test_no_date(self):
        d, src = extract_date("report.pdf")
        assert d is None
        assert src is None
