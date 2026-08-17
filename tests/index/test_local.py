import os
from unittest.mock import patch

from core.index.local import LocalPgVectorStore


class TestLocalPgVectorStore:
    def test_default_connection_string(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("QUERYNEST_DATABASE_URL", None)
            store = LocalPgVectorStore()
            assert "localhost:5432" in store._cs
            assert "querynest" in store._cs

    def test_custom_connection_string(self):
        store = LocalPgVectorStore(connection_string="postgresql://user:pass@myhost:5432/mydb")
        assert store._cs == "postgresql://user:pass@myhost:5432/mydb"
