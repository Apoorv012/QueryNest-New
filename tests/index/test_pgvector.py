import os
from datetime import date
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from core.index.base import (
    DATE_MATCH_IN_RANGE,
    DATE_MATCH_OUT_OF_RANGE,
    DATE_MATCH_UNDATED,
)
from core.index.pgvector import PgVectorStore


class TestPgVectorStore:
    def test_requires_database_url(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("QUERYNEST_DATABASE_URL", None)
            with pytest.raises(RuntimeError, match="QUERYNEST_DATABASE_URL"):
                PgVectorStore()

    def test_custom_connection_string(self):
        store = PgVectorStore(connection_string="postgresql://test:test@localhost:5432/test")
        assert store._cs == "postgresql://test:test@localhost:5432/test"

    def test_env_connection_string(self):
        with patch.dict(os.environ, {"QUERYNEST_DATABASE_URL": "postgresql://env:env@db:5432/env"}):
            store = PgVectorStore()
            assert store._cs == "postgresql://env:env@db:5432/env"

    def _rendered_sql_for(self, date_mode):
        store = PgVectorStore(connection_string="postgresql://test:test@localhost:5432/test")

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        with patch.object(store, "_connect", return_value=mock_conn), \
             patch.object(store, "_release"):
            store.search(
                np.zeros(384),
                "u1",
                top_k=5,
                date_from=date(2020, 1, 1),
                date_to=date(2021, 1, 1),
                date_mode=date_mode,
            )

        return mock_cursor.execute.call_args[0][0].as_string(None)

    def test_undated_tier_selects_only_null_dates(self):
        # D9/D12: undated documents must be reachable. They are served as
        # their own tier rather than folded into the in-range predicate,
        # because an unknown date is not evidence of a match.
        rendered = self._rendered_sql_for(DATE_MATCH_UNDATED)
        assert "document_date IS NULL" in rendered
        assert "IS NOT NULL" not in rendered

    def test_in_range_tier_excludes_undated_documents(self):
        rendered = self._rendered_sql_for(DATE_MATCH_IN_RANGE)
        assert "document_date IS NOT NULL" in rendered
        assert "document_date >= %s" in rendered
        assert "document_date <= %s" in rendered

    def test_out_of_range_tier_selects_dated_rows_outside_the_bounds(self):
        rendered = self._rendered_sql_for(DATE_MATCH_OUT_OF_RANGE)
        assert "document_date IS NOT NULL" in rendered
        assert "document_date < %s" in rendered
        assert "document_date > %s" in rendered

    def test_tiers_are_mutually_exclusive(self):
        # The route concatenates tier results without de-duplicating, which is
        # only safe if no row can satisfy two tiers. NULL vs NOT NULL splits
        # undated from dated; >=/<= vs </> splits in-range from out-of-range.
        undated = self._rendered_sql_for(DATE_MATCH_UNDATED)
        in_range = self._rendered_sql_for(DATE_MATCH_IN_RANGE)
        out_of_range = self._rendered_sql_for(DATE_MATCH_OUT_OF_RANGE)

        assert "document_date IS NULL" in undated
        assert "document_date IS NOT NULL" in in_range
        assert "document_date IS NOT NULL" in out_of_range
        assert in_range != out_of_range

    def test_no_date_predicate_without_a_mode(self):
        # document_date is still SELECTed as a column; what must be absent is
        # any date *predicate* in the WHERE clause.
        rendered = self._rendered_sql_for(None)
        for predicate in (
            "document_date IS NULL",
            "document_date IS NOT NULL",
            "document_date >=",
            "document_date <=",
            "document_date <",
            "document_date >",
        ):
            assert predicate not in rendered, f"unexpected date predicate: {predicate}"
