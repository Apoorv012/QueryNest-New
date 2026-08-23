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

# Chunks are fetched this many times deeper than the requested result count,
# then collapsed to one result per document.
#
# Results are judged per document — the user is looking for a file, not a
# passage — but the store ranks chunks. When one document owns most of the top
# chunks, other documents never surface at all. Measured on the golden sets,
# fetching 5x and then de-duplicating moves Recall@10 from 0.9796 to 1.0000
# (literal) and 0.9186 to 0.9767 (paraphrased), with no metric regressing, for
# about 1.3ms (7.1ms -> 8.4ms at depth 50).
OVERFETCH_FACTOR = 5

def _first_per_document(results: list, limit: int) -> list:
    """Keep the best-scoring chunk per document, preserving rank order."""
    seen: set[str] = set()
    kept = []
    for r in results:
        if r.document_id in seen:
            continue
        seen.add(r.document_id)
        kept.append(r)
        if len(kept) >= limit:
            break
    return kept


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
        results = _first_per_document(
            store.search(
                query_embedding,
                user_id=body.user_id,
                top_k=body.top_k * OVERFETCH_FACTOR,
            ),
            body.top_k,
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
            shortfall = body.top_k - len(results)
            tier = _first_per_document(
                store.search(
                    query_embedding,
                    user_id=body.user_id,
                    top_k=shortfall * OVERFETCH_FACTOR,
                    date_from=date_from,
                    date_to=date_to,
                    date_mode=mode,
                ),
                shortfall,
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
                "filename": r.filename,
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
