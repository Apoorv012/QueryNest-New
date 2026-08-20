from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

from core.index.config import is_store_configured

_has_pgvector = is_store_configured()


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

    # D8: a date expression is a hint, not a hard constraint. When it filters
    # the result set below top_k, backfill the shortfall from an unfiltered
    # search rather than leaving the user with fewer than they asked for.
    # Backfilled results are appended after the in-range ones (both in score
    # order) and clearly marked via `within_date_range`.
    date_filter_applied = date_from is not None or date_to is not None
    if date_filter_applied:
        for r in results:
            r.within_date_range = True

        if len(results) < body.top_k:
            seen_chunk_ids = {r.chunk_id for r in results}
            # Oversample so that even if every unfiltered hit duplicates an
            # in-range result already kept, enough new ones remain to fill
            # up to top_k.
            unfiltered = store.search(
                query_embedding,
                user_id=body.user_id,
                top_k=body.top_k + len(results),
                date_from=None,
                date_to=None,
            )
            for r in unfiltered:
                if len(results) >= body.top_k:
                    break
                if r.chunk_id in seen_chunk_ids:
                    continue
                r.within_date_range = False
                seen_chunk_ids.add(r.chunk_id)
                results.append(r)

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
                "within_date_range": r.within_date_range,
                "source_blocks": [
                    {"text": sb.text, "page": sb.page, "bbox": sb.bbox, "type": sb.type}
                    for sb in r.source_blocks
                ],
            }
            for r in results
        ],
    }
