import json
from unittest.mock import patch

from core.api import ingest_metrics


class TestBuildRecord:
    def test_record_shape(self):
        record = ingest_metrics.build_record(
            filename="report.pdf",
            page_count=10,
            file_bytes=12345,
            chunk_count=7,
            processing_ms=2500.0,
        )
        assert record.filename == "report.pdf"
        assert record.page_count == 10
        assert record.bytes == 12345
        assert record.chunk_count == 7
        assert record.processing_ms == 2500.0
        assert record.git_commit  # non-empty string, either a hash or "unknown"
        assert record.timestamp  # ISO timestamp string

    def test_ms_per_page_computation(self):
        record = ingest_metrics.build_record(
            filename="paper.pdf",
            page_count=5,
            file_bytes=1000,
            chunk_count=3,
            processing_ms=1000.0,
        )
        assert record.ms_per_page == 200.0

    def test_ms_per_page_avoids_divide_by_zero(self):
        record = ingest_metrics.build_record(
            filename="empty.pdf",
            page_count=0,
            file_bytes=100,
            chunk_count=0,
            processing_ms=42.0,
        )
        # Falls back to the raw processing time rather than raising or NaN.
        assert record.ms_per_page == 42.0


class TestRecordIngest:
    def test_appends_one_json_line_per_document(self, tmp_path):
        path = tmp_path / "ingest.json"
        ingest_metrics.record_ingest(
            filename="a.pdf", page_count=2, file_bytes=100,
            chunk_count=1, processing_ms=100.0, path=path,
        )
        ingest_metrics.record_ingest(
            filename="b.pdf", page_count=4, file_bytes=200,
            chunk_count=2, processing_ms=400.0, path=path,
        )

        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        row0 = json.loads(lines[0])
        row1 = json.loads(lines[1])
        assert row0["filename"] == "a.pdf"
        assert row0["ms_per_page"] == 50.0
        assert row1["filename"] == "b.pdf"
        assert row1["ms_per_page"] == 100.0

    def test_creates_parent_dir_if_missing(self, tmp_path):
        path = tmp_path / "nested" / "dir" / "ingest.json"
        assert not path.parent.exists()

        ingest_metrics.record_ingest(
            filename="a.pdf", page_count=1, file_bytes=10,
            chunk_count=1, processing_ms=10.0, path=path,
        )

        assert path.exists()

    def test_write_failure_never_raises(self, tmp_path):
        # Point at a path that cannot be written (parent is actually a file),
        # so mkdir/open must fail — record_ingest must swallow it silently.
        blocker = tmp_path / "blocker"
        blocker.write_text("not a directory")
        bad_path = blocker / "ingest.json"

        # Must not raise.
        ingest_metrics.record_ingest(
            filename="a.pdf", page_count=1, file_bytes=10,
            chunk_count=1, processing_ms=10.0, path=bad_path,
        )

    def test_write_failure_via_mock_never_raises(self, tmp_path):
        path = tmp_path / "ingest.json"
        with patch.object(ingest_metrics, "_append_record", side_effect=OSError("disk full")):
            # Must not raise even though the underlying append blows up.
            ingest_metrics.record_ingest(
                filename="a.pdf", page_count=1, file_bytes=10,
                chunk_count=1, processing_ms=10.0, path=path,
            )
        assert not path.exists()


class TestLoadAndSummarize:
    def test_load_records_missing_file_returns_empty(self, tmp_path):
        assert ingest_metrics.load_records(tmp_path / "nope.json") == []

    def test_load_records_skips_corrupt_lines(self, tmp_path):
        path = tmp_path / "ingest.json"
        path.write_text('{"filename": "a.pdf", "ms_per_page": 10.0}\nnot json\n\n', encoding="utf-8")
        records = ingest_metrics.load_records(path)
        assert len(records) == 1
        assert records[0]["filename"] == "a.pdf"

    def test_summarize_reports_median_and_best(self, tmp_path):
        path = tmp_path / "ingest.json"
        for ms_per_page in (100.0, 200.0, 300.0):
            ingest_metrics.record_ingest(
                filename="a.pdf", page_count=1, file_bytes=10,
                chunk_count=1, processing_ms=ms_per_page, path=path,
            )
        summary = ingest_metrics.summarize(path)
        assert "median 200.0 ms/page" in summary
        assert "best 100.0 ms/page" in summary

    def test_summarize_empty(self, tmp_path):
        summary = ingest_metrics.summarize(tmp_path / "nope.json")
        assert "No ingest metrics" in summary


class TestUploadWiring:
    """Exercises the real _process_file success path (core/api/routes/upload.py),
    with the ingest_metrics internals broken, to prove the call site survives
    an ingest_metrics failure end-to-end — not just the pure function tested
    in isolation above.

    Patches `_append_record` (an internal of ingest_metrics) rather than
    `record_ingest` itself, since `record_ingest` is exactly the function
    responsible for swallowing failures — mocking it away would just prove
    the mock doesn't raise, not that the real swallow works.
    """

    def test_upload_completes_even_if_ingest_metrics_write_fails(self, tmp_path):
        from fastapi.testclient import TestClient

        from core.api import jobs, store
        from core.api.main import app

        store._documents.clear()
        jobs._jobs.clear()

        with patch("core.api.ingest_metrics._append_record", side_effect=OSError("disk full")), \
             patch("core.api.routes.upload._has_pgvector", False), \
             TestClient(app, raise_server_exceptions=False) as client:
            with open("tests/fixtures/small.pdf", "rb") as f:
                resp = client.post(
                    "/upload/bulk",
                    files=[("files", ("t.pdf", f, "application/pdf"))],
                )
            job_id = resp.json()["job_id"]
            status = client.get(f"/upload/{job_id}/status").json()

        assert status["files"][0]["status"] == "done"

        store._documents.clear()
        jobs._jobs.clear()
