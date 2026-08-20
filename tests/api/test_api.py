from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

SMALL_PDF = "tests/fixtures/small.pdf"


@pytest.fixture()
def client():
    from core.api.main import app
    from core.api import store, jobs

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
