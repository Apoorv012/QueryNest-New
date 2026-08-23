from __future__ import annotations

import hashlib
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile

from core.api.deps import validate_user_id

router = APIRouter()

from core.index.config import is_store_configured

_has_pgvector = is_store_configured()

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_FILES_PER_REQUEST = 20
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


class IngestFailed(RuntimeError):
    """Ingest failed after side effects were already written and rolled back.

    Distinct from a plain RuntimeError so the handler can tell "this document
    was cleaned up" from "this blew up somewhere unexpected".
    """


def _rollback_ingest(doc_id: str, user_id: str) -> None:
    """Undo the side effects that precede indexing, best effort.

    Two writes happen before a document is searchable: the in-memory chunk
    entry and the stored PDF. Neither is transactional with the vector store,
    so on an indexing failure they are removed here.

    Deliberately swallows its own failures: a rollback that cannot finish must
    not mask the original error, and must never let the caller report success.
    A leftover PDF is invisible anyway — nothing references a document_id that
    was never indexed.
    """
    from core.api.store import _documents
    from core.storage import get_file_store

    try:
        _documents.pop(doc_id, None)
    except Exception:  # noqa: BLE001, S110 - see docstring
        pass
    try:
        get_file_store().delete(user_id, doc_id)
    except Exception:  # noqa: BLE001, S110 - see docstring
        pass


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

    # Extraction is ~77% of ingest at roughly 1790 ms/page, so re-processing a
    # byte-identical file is the most expensive avoidable work in the pipeline.
    # Hash before doing any of it.
    content_hash = hashlib.sha256(file_data).hexdigest()
    if _has_pgvector:
        try:
            from core.index import get_vector_store

            existing = get_vector_store().find_by_content_hash(user_id, content_hash)
        except Exception:  # noqa: BLE001 - a dedup lookup failure must not block ingest
            existing = None
        if existing is not None:
            update_file_status(
                job_id, index, status="done", document_id=existing,
                was_duplicate=True,
                processing_ms=(time.perf_counter() - start) * 1000,
            )
            return

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
        from core.storage import get_file_store

        save_document(doc_id, filename, chunks)
        get_file_store().save(user_id, doc_id, file_data)

        # Indexing is the last step and the one that makes a document
        # findable. If it fails, roll back the two side effects that already
        # happened (the on-disk PDF and the in-memory chunk entry) so a file is
        # either fully ingested or not ingested at all.
        #
        # The alternative — keeping the extracted work and reporting a partial
        # state — was tried and removed: nothing could act on it. There is no
        # retry path, so the state was unrecoverable except by re-uploading,
        # which redoes the expensive extraction anyway. It also set a trap for
        # content-hash dedup: a stored-but-unindexed document would later match
        # its own hash and short-circuit a re-upload to something still
        # unsearchable.
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
                    content_hash=content_hash,
                    page_count=len(doc.pages),
                )
            # Catch Exception, not (RuntimeError, OSError): psycopg2.Error is
            # neither, and letting it escape used to pin the job at "pending".
            except Exception as e:
                # The original indexing error must always be what surfaces.
                # _rollback_ingest already swallows its own failures, but guard
                # here too: if rollback ever raised, its message would replace
                # the real cause and the user would be told "cannot delete"
                # instead of "connection refused".
                try:
                    _rollback_ingest(doc_id, user_id)
                except Exception:  # noqa: BLE001, S110 - original error wins
                    pass
                raise IngestFailed(f"indexing failed: {e}") from e

        processing_ms = (time.perf_counter() - start) * 1000

        update_file_status(
            job_id,
            index,
            status="done",
            document_id=doc_id,
            detected_date=detected_date.isoformat() if detected_date else None,
            date_source=date_source,
            processing_ms=processing_ms,
        )
        # Phase 3.1 (docs/plan.md): track ingest cost as a regression metric.
        # Observability only — never allowed to affect the upload outcome,
        # hence the swallow-everything try/except inside record_ingest itself.
        from core.api.ingest_metrics import record_ingest

        record_ingest(
            filename=filename,
            page_count=len(doc.pages),
            file_bytes=len(file_data),
            chunk_count=len(chunks),
            processing_ms=processing_ms,
        )
    except (IngestFailed, RuntimeError, OSError, ValueError) as e:
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

    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files: {len(files)} exceeds the "
            f"{MAX_FILES_PER_REQUEST}-file limit per request",
        )

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
                "was_duplicate": f.was_duplicate,
            }
            for f in job.files
        ],
    }
