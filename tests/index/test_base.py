import pytest

from core.index.base import (
    DATE_MATCH_IN_RANGE,
    DATE_MATCH_OUT_OF_RANGE,
    DATE_MATCH_UNDATED,
    DATE_MATCH_UNFILTERED,
    SearchResult,
    VectorStore,
)


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

    def test_date_match_defaults_to_unfiltered(self):
        # D12: with no date filter applied, a result makes no claim about
        # dates at all — it is neither "in range" nor "out of range".
        r = SearchResult(chunk_id=0, document_id="", text="", heading="", score=0.99, page=0)
        assert r.date_match == DATE_MATCH_UNFILTERED

    def test_date_match_carries_three_distinct_states(self):
        # The whole point of D12: "undated" must be distinguishable from
        # "out of range". A boolean collapsed them and claimed a confidence
        # the system does not have about undated documents.
        states = {DATE_MATCH_IN_RANGE, DATE_MATCH_UNDATED, DATE_MATCH_OUT_OF_RANGE}
        assert len(states) == 3
        for state in states:
            r = SearchResult(
                chunk_id=0, document_id="", text="", heading="", score=0.99, page=0,
                date_match=state,
            )
            assert r.date_match == state
