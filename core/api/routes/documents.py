from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel

from core.api.deps import validate_user_id
from core.storage.local import UPLOAD_DIR  # noqa: F401 - re-exported for tests/api/test_api.py

router = APIRouter()

from core.index.config import is_store_configured

_has_pgvector = is_store_configured()


@router.get("/documents")
def list_documents(user_id: str = Depends(validate_user_id)):
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
def list_chunks(doc_id: str, user_id: str = Depends(validate_user_id)):
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
def update_document_date(
    doc_id: str, body: UpdateDateRequest, user_id: str = Depends(validate_user_id)
):
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
def get_document_pdf(
    doc_id: str, user_id: str = Depends(validate_user_id), download: bool = False
):
    from core.storage import get_file_store

    try:
        result = get_file_store().get(user_id, doc_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="PDF not found")

    if isinstance(result, str):
        if download:
            sep = "&" if "?" in result else "?"
            result = f"{result}{sep}download={doc_id}.pdf"
        return RedirectResponse(result)

    headers = (
        {"Content-Disposition": f'attachment; filename="{doc_id}.pdf"'} if download else {}
    )
    return Response(content=result, media_type="application/pdf", headers=headers)
