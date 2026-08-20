import os

# Force pgvector off for the entire test session, regardless of whether
# .env exists or what it contains. This must run before any test module
# imports core.api.main (which calls `load_dotenv()`) — python-dotenv's
# `load_dotenv()` does not override an already-set env var by default, so
# setting it here first wins either way. Without this, `core/api/routes/
# {upload,documents,search}.py` compute `_has_pgvector = bool(os.environ.get(
# "QUERYNEST_DATABASE_URL"))` at import time from whatever is in `.env`, and
# the test suite silently indexes fixture PDFs into a real database
# (docs/plan.md — this was the cause of 35 junk documents landing in
# production Supabase from test runs: test.pdf, a.pdf, b.pdf,
# ../../evil.pdf).
# Both connection-string variables must be cleared, not just the hosted one:
# each storage mode reads its own (QUERYNEST_STORAGE_MODE=local uses
# QUERYNEST_LOCAL_DATABASE_URL), so blanking only one would let the suite see
# a configured store again as soon as .env points at local Docker Postgres.
os.environ["QUERYNEST_DATABASE_URL"] = ""
os.environ["QUERYNEST_LOCAL_DATABASE_URL"] = ""

import pytest

from core.ingest.extractor import extract

SAMPLE_PDF = "tests/fixtures/sample.pdf"


@pytest.fixture(scope="session")
def extracted_doc():
    return extract(SAMPLE_PDF)


@pytest.fixture(autouse=True)
def _block_real_vector_store(monkeypatch):
    """Never let a test construct or reach a real database-backed VectorStore.

    Two independent layers of defense, both scoped to each test:

    1. `QUERYNEST_DATABASE_URL` is kept forced empty (belt-and-suspenders on
       top of the module-level override above, in case some test or fixture
       mutates `os.environ` directly instead of via `monkeypatch`).
    2. `get_vector_store()` itself is replaced with a stub that raises. Some
       existing tests intentionally flip `_has_pgvector` back to True to
       exercise the "database unreachable" code path (e.g.
       TestUpload.test_indexing_failure_reaches_terminal_state_and_is_not_done)
       — those tests patch `core.index.get_vector_store` to a `MagicMock`
       *inside their own `with patch(...)` block*, which shadows this stub
       for their duration and is undone automatically when the block exits.
       No test relies on a real `PgVectorStore`/`LocalPgVectorStore` being
       constructed; ones that unit-test those classes directly (e.g.
       tests/index/test_pgvector.py) instantiate them by hand with a fake
       connection string and mock out `_connect`, never going through
       `get_vector_store()`.
    """
    monkeypatch.setenv("QUERYNEST_DATABASE_URL", "")
    monkeypatch.setenv("QUERYNEST_LOCAL_DATABASE_URL", "")

    def _refuse(*_args, **_kwargs):
        raise RuntimeError(
            "get_vector_store() was called without a fake store patched in. "
            "Tests must never construct a real PgVectorStore/LocalPgVectorStore "
            "— see tests/conftest.py:_block_real_vector_store."
        )

    monkeypatch.setattr("core.index.config.get_vector_store", _refuse)
    monkeypatch.setattr("core.index.get_vector_store", _refuse)
