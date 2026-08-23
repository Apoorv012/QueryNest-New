from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks

from core.api.jobs import Job, create_job
from core.api.routes.upload import UPLOAD_DIR, _process_file

router = APIRouter()

from core.index.config import is_store_configured

_has_pgvector = is_store_configured()
GOLDEN_USER = "golden_user"
EVAL_DIR = Path("data/eval/pdfs")


def _eval_pdf_paths() -> list[Path]:
    """The eval corpus, in one canonical order.

    Both the endpoint (which creates the job's file list) and the worker
    (which reports per-file status by index) must walk the corpus in exactly
    the same order. They previously sorted differently — the endpoint by
    `p.name`, the worker by full path — so once the corpus had
    subdirectories the two orders diverged and every status update was
    recorded against the wrong file.
    """
    return sorted(EVAL_DIR.rglob("*.pdf"))


def _seed_worker(job: Job) -> None:
    from core.index import get_vector_store

    store = get_vector_store()
    store.delete_all_for_user(GOLDEN_USER)

    # _process_file only ever adds files under new doc_ids; a reseed must
    # clear yesterday's PDFs itself or they'd pile up as orphans no row
    # references.
    pdf_dir = UPLOAD_DIR / GOLDEN_USER
    if pdf_dir.is_dir():
        for stale_pdf in pdf_dir.glob("*.pdf"):
            stale_pdf.unlink()

    # Golden-set seeding is ingest for a fixed corpus instead of an upload
    # request, so it drives the exact same per-file pipeline the real
    # `/upload/bulk` route uses — dedup hash, PDF storage, embedding,
    # indexing, rollback-on-failure, ingest metrics — rather than a second
    # copy that silently drifts from it (see git history: it used to skip
    # content_hash/page_count and never wrote the PDF to disk at all).
    for i, pdf_path in enumerate(_eval_pdf_paths()):
        _process_file(job.job_id, i, pdf_path.read_bytes(), pdf_path.name, GOLDEN_USER)


@router.post("/eval/seed")
def seed_golden_set(background_tasks: BackgroundTasks):
    if not _has_pgvector:
        return {"error": "Requires database. Set QUERYNEST_DATABASE_URL."}

    pdf_files = [p.name for p in _eval_pdf_paths()]
    if not pdf_files:
        return {"error": f"No PDFs found in {EVAL_DIR}"}

    job = create_job(GOLDEN_USER, pdf_files)
    background_tasks.add_task(_seed_worker, job)

    return {
        "job_id": job.job_id,
        "user_id": GOLDEN_USER,
        "total": len(pdf_files),
        "message": "Seeding golden set in background",
    }
