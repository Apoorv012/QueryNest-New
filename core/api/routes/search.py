from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.index.base import (
    DATE_MATCH_IN_RANGE,
    DATE_MATCH_OUT_OF_RANGE,
    DATE_MATCH_UNDATED,
)

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
    date_filter_applied = date_from is not None or date_to is not None

    if not date_filter_applied:
        results = store.search(
            query_embedding,
            user_id=body.user_id,
            top_k=body.top_k,
        )
    else:
        # D12: a date expression is a hint, not a hard constraint, so a short
        # result set is topped up from progressively weaker tiers rather than
        # left short. The tiers are served in descending confidence:
        #
        #   1. in_range      - dated, and inside the requested range
        #   2. undated       - no date known, so it *might* match
        #   3. out_of_range  - dated, and known to fall outside
        #
        # Undated documents rank above out-of-range ones deliberately: an
        # unknown date might be the one the user wants, whereas a date outside
        # the range is a verified non-match. (7 of 17 corpus documents
        # currently have no detectable date, so this tier is not an edge case.)
        # The tiers are mutually exclusive in SQL, so no chunk can repeat.
        results = []
        for mode in (
            DATE_MATCH_IN_RANGE,
            DATE_MATCH_UNDATED,
            DATE_MATCH_OUT_OF_RANGE,
        ):
            if len(results) >= body.top_k:
                break
            tier = store.search(
                query_embedding,
                user_id=body.user_id,
                top_k=body.top_k - len(results),
                date_from=date_from,
                date_to=date_to,
                date_mode=mode,
            )
            # Stamp the tier here rather than trusting the store to do it:
            # the route is what decided which tier this call represents, so
            # the label cannot drift if a store implementation forgets.
            for r in tier:
                r.date_match = mode
            results.extend(tier)

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
                "date_match": r.date_match,
                "source_blocks": [
                    {"text": sb.text, "page": sb.page, "bbox": sb.bbox, "type": sb.type}
                    for sb in r.source_blocks
                ],
            }
            for r in results
        ],
    }
