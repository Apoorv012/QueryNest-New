import os
from unittest.mock import patch

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
