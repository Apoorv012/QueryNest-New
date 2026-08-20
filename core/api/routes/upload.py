from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile

from core.api.deps import validate_user_id

router = APIRouter()

_has_pgvector = bool(os.environ.get("QUERYNEST_DATABASE_URL"))

UPLOAD_DIR = Path("data/uploads").resolve()

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
_READ_CHUNK_SIZE = 1024 * 1024


def _read_capped(f: UploadFile, max_bytes: int) -> bytes:
    """Read an upload in chunks, aborting before buffering past max_bytes."""
    chunks = []
    total = 0
    while True:
        chunk = f.file.read(_READ_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"{f.filename} exceeds the {max_bytes // (1024 * 1024)}MB upload limit",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _is_pdf_content(data: bytes) -> bool:
    """Check the PDF signature (%PDF- header, %%EOF trailer) rather than trusting the filename."""
    return data.startswith(b"%PDF-") and b"%%EOF" in data[-2048:]


def _process_file(
    job_id: str,
    index: int,
    file_data: bytes,
    filename: str,
    user_id: str,
) -> None:
    from core.api.jobs import update_file_status
    from core.chunking.chunker import chunk_document
    from core.ingest.date_extractor import extract_date
    from core.ingest.extractor import extract

    start = time.perf_counter()
    doc_id = uuid.uuid4().hex[:12]

    tmp_path = Path("tmp") / f"{doc_id}.pdf"
    tmp_path.parent.mkdir(exist_ok=True)
    tmp_path.write_bytes(file_data)

    try:
        doc = extract(str(tmp_path))
        chunks = chunk_document(doc)

        first_page_text = "\n".join(
            b.text for b in doc.pages[0].blocks[:10]
        ) if doc.pages else None
        detected_date, date_source = extract_date(
            filename, first_page_text=first_page_text
        )

        from core.api.store import save_document
        save_document(doc_id, filename, chunks)

        pdf_dir = (UPLOAD_DIR / user_id).resolve()
        if not pdf_dir.is_relative_to(UPLOAD_DIR):
            raise ValueError(f"Invalid user_id: {user_id!r}")
        pdf_dir.mkdir(parents=True, exist_ok=True)
        (pdf_dir / f"{doc_id}.pdf").write_bytes(file_data)

        index_error: str | None = None
        if _has_pgvector:
            try:
                from core.embedding import FastEmbedEmbedder
                from core.index import get_vector_store

                embedder = FastEmbedEmbedder.get_instance()
                texts = [c.text for c in chunks]
                embeddings = embedder.embed(texts)

                source_blocks_data = []
                for c in chunks:
                    source_blocks_data.append([
                        {
                            "text": b.text,
                            "page": b.page,
                            "bbox": list(b.bbox),
                            "type": b.type,
                        }
                        for b in c.source_blocks
                    ])

                store = get_vector_store()
                store.store_chunks(
                    document_id=doc_id,
                    user_id=user_id,
                    filename=filename,
                    texts=texts,
                    embeddings=embeddings,
                    headings=[c.heading for c in chunks],
                    pages=[c.source_blocks[0].page if c.source_blocks else 0 for c in chunks],
                    chunk_indices=[c.chunk_index for c in chunks],
                    document_date=detected_date,
                    source_blocks=source_blocks_data,
                )
            # Any embed/store failure (including psycopg2.Error, which is
            # neither RuntimeError nor OSError) must not report "done".
            except Exception as e:  # noqa: BLE001
                index_error = str(e)

        if index_error is not None:
            update_file_status(
                job_id,
                index,
                status="indexed_partially",
                document_id=doc_id,
                detected_date=detected_date.isoformat() if detected_date else None,
                date_source=date_source,
                error=index_error,
                processing_ms=(time.perf_counter() - start) * 1000,
            )
        else:
            update_file_status(
                job_id,
                index,
                status="done",
                document_id=doc_id,
                detected_date=detected_date.isoformat() if detected_date else None,
                date_source=date_source,
                processing_ms=(time.perf_counter() - start) * 1000,
            )
    except (RuntimeError, OSError, ValueError) as e:
        update_file_status(
            job_id,
            index,
            status="error",
            error=str(e),
            processing_ms=(time.perf_counter() - start) * 1000,
        )
    finally:
        tmp_path.unlink(missing_ok=True)


@router.post("/upload/bulk")
def upload_bulk(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    user_id: str = Depends(validate_user_id),
):
    from core.api.jobs import create_job

    pdf_files = [f for f in files if f.filename and f.filename.lower().endswith(".pdf")]
    if not pdf_files:
        raise HTTPException(status_code=400, detail="No PDF files provided")

    file_data_list = []
    for f in pdf_files:
        data = _read_capped(f, MAX_UPLOAD_BYTES)
        if _is_pdf_content(data):
            file_data_list.append((data, f.filename or "unknown"))

    if not file_data_list:
        raise HTTPException(status_code=400, detail="No valid PDF files provided")

    job = create_job(user_id, [name for _, name in file_data_list])

    for i, (data, filename) in enumerate(file_data_list):
        background_tasks.add_task(_process_file, job.job_id, i, data, filename, user_id)

    return {"job_id": job.job_id, "total": len(file_data_list)}


@router.get("/upload/{job_id}/status")
def upload_status(job_id: str):
    from core.api.jobs import get_job

    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": job.job_id,
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
                "date_source": f.date_source,
                "error": f.error,
                "processing_ms": f.processing_ms,
            }
            for f in job.files
        ],
    }
