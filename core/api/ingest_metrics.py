"""Phase 3.1: persist ingest cost as a tracked regression metric.

The pipeline already measures `processing_ms` per file (see
`core/api/jobs.py:FileStatus.processing_ms`, set in
`core/api/routes/upload.py`). Historically that number was surfaced once in a
job-status response and then discarded. This module appends one JSON record
per successfully ingested document to `reports/ingest.json`, so ingest cost
across commits can be compared rather than eyeballed.

Report **ms per page, not ms per file** (docs/plan.md Phase 3.1): the corpus
spans 2-43 page documents, and per-file timings vary ~4x for reasons that
have nothing to do with code changes.

Writing metrics must never fail an upload — this is observability, not core
function. Every public function here swallows its own errors.
"""

from __future__ import annotations

import json
import statistics
import threading
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

REPORTS_DIR = Path("reports")
INGEST_METRICS_PATH = REPORTS_DIR / "ingest.json"

# BackgroundTasks in core/api/routes/upload.py run in a shared thread pool
# within one process, so a thread lock is enough to serialize the
# read/append below within this process. The single-line append itself is
# additionally sized to stay within a single small write() syscall, which is
# atomic with respect to any other process appending to the same file.
_write_lock = threading.Lock()


@dataclass
class IngestRecord:
    filename: str
    page_count: int
    bytes: int
    chunk_count: int
    processing_ms: float
    ms_per_page: float
    git_commit: str
    timestamp: str


def _get_git_commit() -> str:
    """Best-effort git short hash. Mirrors core/eval/runner.get_git_commit
    (read-only import — that module is off-limits to modify here, and this
    keeps ingest_metrics free of any dependency on the eval package).
    """
    import subprocess

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        commit = result.stdout.strip()
        return commit or "unknown"
    except (subprocess.SubprocessError, OSError):
        return "unknown"


def build_record(
    *,
    filename: str,
    page_count: int,
    file_bytes: int,
    chunk_count: int,
    processing_ms: float,
) -> IngestRecord:
    """Pure construction of an IngestRecord — no I/O, easy to unit test."""
    ms_per_page = processing_ms / page_count if page_count > 0 else float(processing_ms)
    return IngestRecord(
        filename=filename,
        page_count=page_count,
        bytes=file_bytes,
        chunk_count=chunk_count,
        processing_ms=processing_ms,
        ms_per_page=ms_per_page,
        git_commit=_get_git_commit(),
        timestamp=datetime.now(UTC).isoformat(),
    )


def _append_record(record: IngestRecord, path: Path) -> None:
    """Append one JSON line to `path`, creating parent dirs/file if needed.

    Uses line-delimited JSON (one record per line) rather than a single JSON
    array: appending a line is an atomic, lock-free-safe operation on POSIX
    and on Windows for small writes, whereas appending to a JSON array
    requires read-modify-write of the whole file, which corrupts under
    concurrent writers (uploads run in a background thread pool — see
    core/api/routes/upload.py's use of BackgroundTasks).
    """
    line = json.dumps(asdict(record))
    with _write_lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        # O_APPEND (mode "a") makes each write() atomic with respect to other
        # appenders, as long as the write is a single syscall — one line is
        # always small enough for that to hold. The lock above additionally
        # serializes same-process writers so mkdir/open never race.
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def record_ingest(
    *,
    filename: str,
    page_count: int,
    file_bytes: int,
    chunk_count: int,
    processing_ms: float,
    path: Path = INGEST_METRICS_PATH,
) -> None:
    """Record one successfully-ingested document. Never raises.

    This is the entry point wired into core/api/routes/upload.py. Any
    failure (disk full, permissions, whatever) is swallowed: observability
    must never be able to fail an upload.
    """
    try:
        record = build_record(
            filename=filename,
            page_count=page_count,
            file_bytes=file_bytes,
            chunk_count=chunk_count,
            processing_ms=processing_ms,
        )
        _append_record(record, path)
    except Exception:  # noqa: BLE001, S110 - observability must never break ingest
        pass


def load_records(path: Path = INGEST_METRICS_PATH) -> list[dict]:
    """Read all recorded ingest rows. Missing/corrupt lines are skipped."""
    if not path.exists():
        return []
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def summarize(path: Path = INGEST_METRICS_PATH) -> str:
    """Human-readable median and best-ever ms/page, so a regression in ingest
    cost shows up as a number instead of a vague feeling that uploads got
    slower.
    """
    records = load_records(path)
    if not records:
        return "No ingest metrics recorded yet."

    ms_per_page = [r["ms_per_page"] for r in records if "ms_per_page" in r]
    if not ms_per_page:
        return "No ingest metrics recorded yet."

    median = statistics.median(ms_per_page)
    best = min(ms_per_page)
    return (
        f"Ingest metrics ({len(records)} documents): "
        f"median {median:.1f} ms/page, best {best:.1f} ms/page"
    )


def print_summary(path: Path = INGEST_METRICS_PATH) -> None:
    print(summarize(path))


if __name__ == "__main__":  # pragma: no cover - manual invocation only
    print_summary()
