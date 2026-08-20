from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

router = APIRouter()

_has_pgvector = bool(os.environ.get("QUERYNEST_DATABASE_URL"))

UPLOAD_DIR = Path("data/uploads")


@router.get("/documents")
def list_documents(user_id: str = "dev-user"):
    if not _has_pgvector:
        raise HTTPException(
            status_code=503, detail="Requires database. Set QUERYNEST_DATABASE_URL."
        )

    from core.index import get_vector_store

    store = get_vector_store()
    docs = store.list_documents(user_id)

    return {
        "documents": [
            {
                "document_id": d.document_id,
                "filename": d.filename,
                "document_date": d.document_date.isoformat() if d.document_date else None,
                "chunk_count": d.chunk_count,
            }
            for d in docs
        ]
    }


@router.get("/documents/{doc_id}/chunks")
def list_chunks(doc_id: str, user_id: str = "dev-user"):
    from core.api.store import get_chunks

    chunks = get_chunks(doc_id)
    if chunks is None:
        raise HTTPException(status_code=404, detail="Document not found")

    return {
        "chunks": [
            {
                "chunk_index": c.chunk_index,
                "heading": c.heading,
                "text": c.text,
                "block_count": len(c.source_blocks),
                "blocks": [
                    {
                        "text": b.text,
                        "page": b.page,
                        "bbox": list(b.bbox),
                        "type": b.type,
                    }
                    for b in c.source_blocks
                ],
            }
            for c in chunks
        ]
    }


class UpdateDateRequest(BaseModel):
    date: str | None = None


@router.patch("/documents/{doc_id}/date")
def update_document_date(doc_id: str, body: UpdateDateRequest, user_id: str = "dev-user"):
    if not _has_pgvector:
        raise HTTPException(
            status_code=503, detail="Requires database. Set QUERYNEST_DATABASE_URL."
        )

    from core.index import get_vector_store

    doc_date = date.fromisoformat(body.date) if body.date else None
    store = get_vector_store()
    store.update_document_date(doc_id, user_id, doc_date)

    return {"document_id": doc_id, "date": body.date}


@router.get("/documents/{doc_id}/pdf")
def get_document_pdf(doc_id: str, user_id: str = "dev-user"):
    pdf_path = UPLOAD_DIR / user_id / f"{doc_id}.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(pdf_path, media_type="application/pdf", filename=f"{doc_id}.pdf")
