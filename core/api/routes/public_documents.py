from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse, Response

from core.api.constants import GOLDEN_USER
from core.index.config import is_store_configured

router = APIRouter()

_has_pgvector = is_store_configured()


@router.get("/documents")
def list_public_documents():
    """Read-only listing of the golden demo corpus. No user_id parameter."""
    if not _has_pgvector:
        return {"documents": []}

    from core.index import get_vector_store

    docs = get_vector_store().list_documents(GOLDEN_USER)
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


@router.get("/documents/{doc_id}/pdf")
def get_public_document_pdf(doc_id: str, download: bool = False):
    """Read-only PDF fetch, scoped to the golden demo corpus only.

    No user_id is accepted from the client at all — unlike the full API's
    equivalent route, there's nothing to validate or scope, so this can only
    ever serve golden_user's own documents.
    """
    from core.storage import get_file_store

    try:
        result = get_file_store().get(GOLDEN_USER, doc_id)
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
