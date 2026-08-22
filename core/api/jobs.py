from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field


@dataclass
class FileStatus:
    filename: str
    status: str = "pending"
    document_id: str | None = None
    detected_date: str | None = None
    date_source: str | None = None
    error: str | None = None
    processing_ms: float | None = None


@dataclass
class Job:
    job_id: str
    user_id: str
    total: int
    files: list[FileStatus] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def completed(self) -> int:
        return sum(1 for f in self.files if f.status == "done")

    @property
    def failed(self) -> int:
        return sum(1 for f in self.files if f.status == "error")

    @property
    def status(self) -> str:
        # Ingest is atomic: a file is either fully ingested ("done") or rolled
        # back ("error"). There is no third terminal state — see _process_file.
        if self.failed == self.total:
            return "failed"
        if self.completed + self.failed == self.total:
            return "done"
        return "processing"


_jobs: dict[str, Job] = {}
_jobs_lock = threading.Lock()


def create_job(user_id: str, filenames: list[str]) -> Job:
    job_id = uuid.uuid4().hex[:12]
    job = Job(
        job_id=job_id,
        user_id=user_id,
        total=len(filenames),
        files=[FileStatus(filename=f) for f in filenames],
    )
    with _jobs_lock:
        _jobs[job_id] = job
    return job


def get_job(job_id: str) -> Job | None:
    with _jobs_lock:
        return _jobs.get(job_id)


def update_file_status(
    job_id: str,
    index: int,
    *,
    status: str,
    document_id: str | None = None,
    detected_date: str | None = None,
    date_source: str | None = None,
    error: str | None = None,
    processing_ms: float | None = None,
) -> None:
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return
    with job._lock:
        f = job.files[index]
        f.status = status
        if document_id is not None:
            f.document_id = document_id
        if detected_date is not None:
            f.detected_date = detected_date
        if date_source is not None:
            f.date_source = date_source
        if error is not None:
            f.error = error
        if processing_ms is not None:
            f.processing_ms = processing_ms
