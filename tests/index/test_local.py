import os
from unittest.mock import patch

import pytest

from core.index.local import LocalPgVectorStore


class TestLocalPgVectorStore:
    def test_requires_local_database_url(self):
        # Local mode has no implicit default: a missing connection string is
        # an error, not a silent fallback.
        with (
            patch.dict(os.environ, {}, clear=True),
            pytest.raises(RuntimeError, match="QUERYNEST_LOCAL_DATABASE_URL"),
        ):
            LocalPgVectorStore()

    def test_reads_local_database_url(self):
        with patch.dict(
            os.environ,
            {"QUERYNEST_LOCAL_DATABASE_URL": "postgresql://a:b@localhost:5433/c"},
            clear=True,
        ):
            assert LocalPgVectorStore()._cs == "postgresql://a:b@localhost:5433/c"

    def test_never_falls_back_to_hosted_database_url(self):
        # Regression: LocalPgVectorStore used to fall back to
        # QUERYNEST_DATABASE_URL, so QUERYNEST_STORAGE_MODE=local silently
        # connected to the hosted/Supabase database instead of the local one.
        with (
            patch.dict(
                os.environ,
                {"QUERYNEST_DATABASE_URL": "postgresql://prod:prod@supabase.example:5432/prod"},
                clear=True,
            ),
            pytest.raises(RuntimeError, match="QUERYNEST_LOCAL_DATABASE_URL"),
        ):
            LocalPgVectorStore()

    def test_custom_connection_string(self):
        store = LocalPgVectorStore(connection_string="postgresql://user:pass@myhost:5432/mydb")
        assert store._cs == "postgresql://user:pass@myhost:5432/mydb"
