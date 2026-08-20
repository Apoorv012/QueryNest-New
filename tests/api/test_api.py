from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

SMALL_PDF = "tests/fixtures/small.pdf"


@pytest.fixture()
def client():
    from core.api import jobs, store
    from core.api.main import app

    store._documents.clear()
    jobs._jobs.clear()

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    store._documents.clear()
    jobs._jobs.clear()


def _upload_pdf(client, filename="test.pdf", path=SMALL_PDF):
    with open(path, "rb") as f:
        resp = client.post(
            "/upload/bulk",
            files=[("files", (filename, f, "application/pdf"))],
        )
    return resp.json()


def _get_doc_id(client, job_id):
    status = client.get(f"/upload/{job_id}/status").json()
    return status["files"][0]["document_id"]


class TestHealth:
    def test_root(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "QueryNest API"
        assert "version" in data

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestUpload:
    def test_rejects_non_pdf(self, client):
        resp = client.post(
            "/upload/bulk",
            files=[("files", ("notes.txt", b"hello", "text/plain"))],
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "No PDF files provided"

    def test_rejects_fake_pdf_content(self, client):
        resp = client.post(
            "/upload/bulk",
            files=[("files", ("fake.pdf", b"not actually a pdf", "application/pdf"))],
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "No valid PDF files provided"

    def test_rejects_oversized_upload(self, client):
        with open(SMALL_PDF, "rb") as f:
            content = f.read()
        with patch("core.api.routes.upload.MAX_UPLOAD_BYTES", 10):
            resp = client.post(
                "/upload/bulk",
                files=[("files", ("big.pdf", content, "application/pdf"))],
            )
        assert resp.status_code == 400
        assert "exceeds" in resp.json()["detail"]

    def test_traversal_filename_is_sanitized(self, client):
        data = _upload_pdf(client, filename="../../evil.pdf")
        job_id = data["job_id"]

        status = client.get(f"/upload/{job_id}/status").json()
        assert status["status"] == "done"
        assert status["files"][0]["status"] == "done"

    def test_empty_body_returns_422(self, client):
        resp = client.post("/upload/bulk")
        assert resp.status_code == 422

    def test_single_pdf(self, client):
        data = _upload_pdf(client)
        assert "job_id" in data
        assert data["total"] == 1

    def test_multiple_pdfs(self, client):
        with open(SMALL_PDF, "rb") as f:
            content = f.read()
        resp = client.post(
            "/upload/bulk",
            files=[
                ("files", ("a.pdf", content, "application/pdf")),
                ("files", ("b.pdf", content, "application/pdf")),
            ],
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_indexing_failure_reaches_terminal_state_and_is_not_done(self, client):
        # A DB error during embed/store used to be swallowed by
        # `except (RuntimeError, OSError): pass`, still marking the file
        # "done" while it was never made searchable — and a psycopg2.Error
        # (neither RuntimeError nor OSError) escaped both handlers entirely,
        # pinning the job at "pending" forever (docs/plan.md 0.2).
        from unittest.mock import MagicMock

        class FakeDbError(Exception):
            pass

        fake_store = MagicMock()
        fake_store.store_chunks.side_effect = FakeDbError("connection refused")

        with patch("core.api.routes.upload._has_pgvector", True), \
             patch("core.index.get_vector_store", return_value=fake_store):
            data = _upload_pdf(client)
        job_id = data["job_id"]

        status = client.get(f"/upload/{job_id}/status").json()
        assert status["status"] in ("done", "failed")  # terminal, not "processing"
        file_status = status["files"][0]
        assert file_status["status"] != "done"
        assert file_status["status"] == "indexed_partially"
        assert file_status["error"] is not None
        assert "connection refused" in file_status["error"]

    def test_upload_never_constructs_a_real_vector_store(self, client):
        # Regression guard for the leak where `_has_pgvector` (computed at
        # import time from QUERYNEST_DATABASE_URL) was True whenever `.env`
        # carried a real Supabase URL, so plain `pytest` runs indexed test
        # fixtures into production (docs/plan.md: 35 junk documents —
        # test.pdf, a.pdf, b.pdf, ../../evil.pdf — came from test runs).
        # tests/conftest.py now forces QUERYNEST_DATABASE_URL empty for the
        # whole session and replaces `get_vector_store` with a stub that
        # raises; assert here that a normal upload never even calls it, and
        # that `_has_pgvector` reflects the forced-off env var.
        import core.api.routes.upload as upload_route

        assert upload_route._has_pgvector is False

        with patch("core.index.get_vector_store") as mock_get_store:
            data = _upload_pdf(client)
            job_id = data["job_id"]
            status = client.get(f"/upload/{job_id}/status").json()

        assert status["files"][0]["status"] == "done"
        mock_get_store.assert_not_called()

    def test_job_completes(self, client):
        data = _upload_pdf(client)
        job_id = data["job_id"]

        status = client.get(f"/upload/{job_id}/status").json()
        assert status["status"] == "done"
        assert status["completed"] == 1
        assert status["failed"] == 0
        assert status["files"][0]["status"] == "done"
        assert status["files"][0]["document_id"] is not None
        assert status["files"][0]["processing_ms"] is not None
        assert status["files"][0]["processing_ms"] > 0

    def test_nonexistent_job_returns_error(self, client):
        resp = client.get("/upload/nonexistent-id/status")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Job not found"

    def test_document_has_chunks(self, client):
        data = _upload_pdf(client)
        doc_id = _get_doc_id(client, data["job_id"])

        resp = client.get(f"/documents/{doc_id}/chunks")
        assert resp.status_code == 200
        chunks = resp.json()["chunks"]
        assert len(chunks) > 0

        chunk = chunks[0]
        assert "chunk_index" in chunk
        assert "heading" in chunk
        assert "text" in chunk
        assert "blocks" in chunk
        assert len(chunk["blocks"]) > 0

    def test_pdf_is_downloadable(self, client):
        data = _upload_pdf(client)
        doc_id = _get_doc_id(client, data["job_id"])

        resp = client.get(f"/documents/{doc_id}/pdf")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"


class TestDocuments:
    def test_chunks_nonexistent_document(self, client):
        resp = client.get("/documents/fake-id/chunks")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Document not found"

    def test_pdf_nonexistent_document(self, client):
        resp = client.get("/documents/fake-id/pdf")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "PDF not found"

    @pytest.mark.parametrize("traversal_user_id", ["..", "../..", "a/../.."])
    def test_pdf_rejects_path_traversal_user_id(self, client, traversal_user_id):
        # GET /documents/{doc_id}/pdf used to resolve UPLOAD_DIR / user_id /
        # f"{doc_id}.pdf" without validating user_id, so a traversal value
        # could serve any .pdf on disk outside the upload directory
        # (docs/plan.md 0.1, verified reproducing pre-fix).
        import core.api.routes.documents as documents_route

        # Plant a "secret" PDF at every directory a traversal in this
        # parametrization could reach, so a regression that starts serving
        # bytes again is caught regardless of which level it escapes to.
        candidates = [
            documents_route.UPLOAD_DIR.parent / "secret_outside.pdf",
            documents_route.UPLOAD_DIR.parent.parent / "secret_outside.pdf",
        ]
        for path in candidates:
            path.write_bytes(b"%PDF-1.4 secret %%EOF")
        try:
            resp = client.get(
                "/documents/secret_outside/pdf",
                params={"user_id": traversal_user_id},
            )
            assert 400 <= resp.status_code < 500
            assert b"secret" not in resp.content
        finally:
            for path in candidates:
                path.unlink(missing_ok=True)

    def test_list_documents_no_db(self, client):
        with patch("core.api.routes.documents._has_pgvector", False):
            resp = client.get("/documents")
            assert resp.status_code == 503
            assert "detail" in resp.json()

    def test_update_date_no_db(self, client):
        with patch("core.api.routes.documents._has_pgvector", False):
            resp = client.patch(
                "/documents/fake-id/date",
                json={"date": "2024-01-01"},
            )
            assert resp.status_code == 503
            assert "detail" in resp.json()


class TestSearch:
    def test_empty_query(self, client):
        with patch("core.api.routes.search._has_pgvector", True):
            resp = client.post("/search", json={"query": ""})
            assert resp.status_code == 400
            assert resp.json()["detail"] == "Query cannot be empty"

    def test_whitespace_query(self, client):
        with patch("core.api.routes.search._has_pgvector", True):
            resp = client.post("/search", json={"query": "   "})
            assert resp.status_code == 400
            assert resp.json()["detail"] == "Query cannot be empty"

    def test_search_no_db(self, client):
        with patch("core.api.routes.search._has_pgvector", False):
            resp = client.post("/search", json={"query": "attention mechanism"})
            assert resp.status_code == 503
            assert "detail" in resp.json()

    def test_search_missing_body(self, client):
        resp = client.post("/search")
        assert resp.status_code == 422

    def test_search_rejects_empty_when_no_db(self, client):
        with patch("core.api.routes.search._has_pgvector", False):
            resp = client.post("/search", json={"query": ""})
            assert resp.status_code == 400
            assert resp.json()["detail"] == "Query cannot be empty"


class TestSearchBackfill:
    """D8: date-filtered results short of top_k get backfilled from an
    unfiltered search, appended after the in-range results and clearly
    marked via `within_date_range` (docs/plan.md D8 / task 2.6)."""

    @staticmethod
    def _result(chunk_id, score):
        from core.index.base import SearchResult

        return SearchResult(
            chunk_id=chunk_id,
            document_id=f"doc{chunk_id}",
            text=f"text {chunk_id}",
            heading="h",
            score=score,
            page=0,
        )

    def _search(self, client, fake_store, body):
        fake_embedder = MagicMock()
        fake_embedder.embed_query.return_value = [0.0] * 384

        with patch("core.api.routes.search._has_pgvector", True), \
             patch("core.index.get_vector_store", return_value=fake_store), \
             patch(
                 "core.embedding.FastEmbedEmbedder.get_instance",
                 return_value=fake_embedder,
             ):
            return client.post("/search", json=body)

    def test_backfills_short_date_filtered_results(self, client):
        in_range = [self._result(1, 0.9), self._result(2, 0.8)]
        # The unfiltered rerun naturally includes the same top hits again
        # (chunk_id 1, 2) plus new ones — duplicates must be skipped.
        unfiltered = [
            self._result(1, 0.9),
            self._result(2, 0.8),
            self._result(3, 0.7),
            self._result(4, 0.6),
            self._result(5, 0.5),
        ]
        fake_store = MagicMock()
        fake_store.search.side_effect = [in_range, unfiltered]

        resp = self._search(
            client,
            fake_store,
            {"query": "invoices in 2020", "top_k": 5, "user_id": "u1"},
        )

        assert resp.status_code == 200
        results = resp.json()["results"]
        assert [r["chunk_id"] for r in results] == [1, 2, 3, 4, 5]
        assert [r["within_date_range"] for r in results] == [
            True, True, False, False, False,
        ]

        assert fake_store.search.call_count == 2
        second_call = fake_store.search.call_args_list[1]
        assert second_call.kwargs["date_from"] is None
        assert second_call.kwargs["date_to"] is None
        # Oversampled by the shortfall (top_k=5 + 2 already-kept in-range
        # results) so duplicates don't starve the backfill.
        assert second_call.kwargs["top_k"] == 7

    def test_no_second_query_when_already_at_top_k(self, client):
        in_range = [self._result(i, 1.0 - i / 10) for i in range(5)]
        fake_store = MagicMock()
        fake_store.search.return_value = in_range

        resp = self._search(
            client,
            fake_store,
            {"query": "invoices in 2020", "top_k": 5, "user_id": "u1"},
        )

        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) == 5
        assert all(r["within_date_range"] for r in results)
        fake_store.search.assert_called_once()

    def test_no_backfill_without_date_filter(self, client):
        # No date expression in the query and no explicit date_from/date_to
        # -> behaves exactly as before: single query, no backfill logic.
        few_results = [self._result(1, 0.9), self._result(2, 0.8)]
        fake_store = MagicMock()
        fake_store.search.return_value = few_results

        resp = self._search(
            client,
            fake_store,
            {"query": "insurance policy", "top_k": 5, "user_id": "u1"},
        )

        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) == 2
        assert all(r["within_date_range"] for r in results)
        fake_store.search.assert_called_once()
