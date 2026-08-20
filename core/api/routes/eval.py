from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks

from core.api.jobs import Job, create_job, get_job, update_file_status

router = APIRouter()

from core.index.config import is_store_configured

_has_pgvector = is_store_configured()
GOLDEN_USER = "golden_user"
EVAL_DIR = Path("data/eval/pdfs")


def _seed_worker(job: Job) -> None:
    from core.chunking.chunker import chunk_document
    from core.embedding import FastEmbedEmbedder
    from core.index import get_vector_store
    from core.ingest.date_extractor import extract_date
    from core.ingest.extractor import extract

    store = get_vector_store()
    embedder = FastEmbedEmbedder.get_instance()

    store.delete_all_for_user(GOLDEN_USER)

    pdf_files = sorted(
        p for p in EVAL_DIR.rglob("*.pdf")
    )

    for i, pdf_path in enumerate(pdf_files):
        filename = pdf_path.name
        try:
            doc = extract(str(pdf_path))
            chunks = chunk_document(doc)
            if not chunks:
                update_file_status(job.job_id, i, status="error", error="No chunks produced")
                continue

            doc_id = uuid.uuid4().hex[:12]

            first_page_text = "\n".join(
                b.text for b in doc.pages[0].blocks[:10]
            ) if doc.pages else None
            detected_date, date_source = extract_date(
                filename, first_page_text=first_page_text
            )

            texts = [c.text for c in chunks]
            embeddings = embedder.embed(texts)

            source_blocks_data = [
                [
                    {"text": b.text, "page": b.page, "bbox": list(b.bbox), "type": b.type}
                    for b in c.source_blocks
                ]
                for c in chunks
            ]

            store.store_chunks(
                document_id=doc_id,
                user_id=GOLDEN_USER,
                filename=filename,
                texts=texts,
                embeddings=embeddings,
                headings=[c.heading for c in chunks],
                pages=[c.source_blocks[0].page if c.source_blocks else 0 for c in chunks],
                chunk_indices=[c.chunk_index for c in chunks],
                document_date=detected_date,
                source_blocks=source_blocks_data,
            )

            update_file_status(
                job.job_id, i, status="done",
                document_id=doc_id,
                detected_date=detected_date.isoformat() if detected_date else None,
                date_source=date_source,
            )
        except (RuntimeError, OSError, ValueError) as e:
            update_file_status(job.job_id, i, status="error", error=str(e))


@router.post("/eval/seed")
def seed_golden_set(background_tasks: BackgroundTasks):
    if not _has_pgvector:
        return {"error": "Requires database. Set QUERYNEST_DATABASE_URL."}

    pdf_files = sorted(p.name for p in EVAL_DIR.rglob("*.pdf"))
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


@router.get("/eval/seed/{job_id}/status")
def seed_status(job_id: str):
    job = get_job(job_id)
    if job is None:
        return {"error": "Job not found"}

    return {
        "job_id": job.job_id,
        "user_id": job.user_id,
        "status": job.status,
        "total": job.total,
        "completed": job.completed,
        "failed": job.failed,
        "files": [
            {
                "filename": f.filename,
                "status": f.status,
                "document_id": f.document_id,
                "detected_date": f.detected_date,
                "error": f.error,
            }
            for f in job.files
        ],
    }
