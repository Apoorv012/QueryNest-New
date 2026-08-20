import os
from datetime import date
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

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

    def test_date_filtered_search_does_not_exclude_null_dates(self):
        # document_date IS NULL used to make SQL "NULL >= x" evaluate false,
        # silently dropping undated documents from any date-filtered search
        # (docs/plan.md 0.3 / D9). The WHERE clause must admit NULLs.
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
            )

        query = mock_cursor.execute.call_args[0][0]
        rendered = query.as_string(None)
        assert "document_date IS NULL OR document_date >= %s" in rendered
        assert "document_date IS NULL OR document_date <= %s" in rendered
