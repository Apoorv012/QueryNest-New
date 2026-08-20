from __future__ import annotations

import os
from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

_has_pgvector = bool(os.environ.get("QUERYNEST_DATABASE_URL"))


class SearchRequest(BaseModel):
    query: str = ""
    top_k: int = 5
    date_from: str | None = None
    date_to: str | None = None
    user_id: str = "dev-user"


@router.post("/search")
def search(body: SearchRequest):
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    if not _has_pgvector:
        raise HTTPException(
            status_code=503, detail="Search requires database. Set QUERYNEST_DATABASE_URL."
        )

    from core.query.parser import parse_query

    parsed = parse_query(body.query)

    date_from = date.fromisoformat(body.date_from) if body.date_from else parsed.date_from
    date_to = date.fromisoformat(body.date_to) if body.date_to else parsed.date_to

    from core.embedding import FastEmbedEmbedder
    from core.index import get_vector_store

    embedder = FastEmbedEmbedder.get_instance()
    query_embedding = embedder.embed_query(parsed.query)

    store = get_vector_store()
    results = store.search(
        query_embedding,
        user_id=body.user_id,
        top_k=body.top_k,
        date_from=date_from,
        date_to=date_to,
    )

    return {
        "query": body.query,
        "parsed_query": parsed.query,
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "results": [
            {
                "chunk_id": r.chunk_id,
                "document_id": r.document_id,
                "text": r.text,
                "heading": r.heading,
                "score": r.score,
                "page": r.page,
                "document_date": r.document_date.isoformat() if r.document_date else None,
                "source_blocks": [
                    {"text": sb.text, "page": sb.page, "bbox": sb.bbox, "type": sb.type}
                    for sb in r.source_blocks
                ],
            }
            for r in results
        ],
    }
