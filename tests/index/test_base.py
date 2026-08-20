import pytest

from core.index.base import SearchResult, VectorStore


class TestVectorStore:
    def test_is_abstract(self):
        with pytest.raises(TypeError):
            VectorStore()


class TestSearchResult:
    def test_construction(self):
        r = SearchResult(
            chunk_id=1,
            document_id="abc123",
            text="test text",
            heading="Introduction",
            score=0.85,
            page=0,
        )
        assert r.chunk_id == 1
        assert r.document_id == "abc123"
        assert r.text == "test text"
        assert r.heading == "Introduction"
        assert r.score == 0.85
        assert r.page == 0

    def test_score_is_float(self):
        r = SearchResult(chunk_id=0, document_id="", text="", heading="", score=0.99, page=0)
        assert isinstance(r.score, float)

    def test_within_date_range_defaults_true(self):
        # D8: a result is "in range" unless explicitly marked as a backfill
        # candidate, so unfiltered searches (and filtered searches that
        # don't need backfill) need no special-casing.
        r = SearchResult(chunk_id=0, document_id="", text="", heading="", score=0.99, page=0)
        assert r.within_date_range is True

    def test_within_date_range_can_be_set_false(self):
        r = SearchResult(
            chunk_id=0, document_id="", text="", heading="", score=0.99, page=0,
            within_date_range=False,
        )
        assert r.within_date_range is False
