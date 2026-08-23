from __future__ import annotations

import threading
import time
from datetime import date

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from core.api.constants import GOLDEN_USER
from core.api.routes.search import OVERFETCH_FACTOR, _first_per_document
from core.index.base import DATE_MATCH_IN_RANGE, DATE_MATCH_OUT_OF_RANGE, DATE_MATCH_UNDATED
from core.index.config import is_store_configured

router = APIRouter()

_has_pgvector = is_store_configured()

# Single-instance, in-memory fixed-window limiter: this route has no auth at
# all, so it needs some floor against casual abuse of embedding + DB calls.
# A real multi-instance deployment would need a shared store instead.
_RATE_LIMIT = 20  # requests
_RATE_WINDOW_S = 60
_lock = threading.Lock()
_hits: dict[str, list[float]] = {}


def _check_rate_limit(ip: str) -> None:
    now = time.monotonic()
    with _lock:
        recent = [t for t in _hits.get(ip, []) if now - t < _RATE_WINDOW_S]
        if len(recent) >= _RATE_LIMIT:
            raise HTTPException(status_code=429, detail="Too many requests, try again shortly")
        recent.append(now)
        _hits[ip] = recent


class PublicSearchRequest(BaseModel):
    query: str = ""
    top_k: int = 5
    date_from: str | None = None
    date_to: str | None = None


@router.post("/search")
def public_search(body: PublicSearchRequest, request: Request):
    _check_rate_limit(request.client.host if request.client else "unknown")

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
    # user_id is never taken from the client: this endpoint can only ever
    # search the golden demo corpus.
    top_k = min(body.top_k, 20)
    date_filter_applied = date_from is not None or date_to is not None

    if not date_filter_applied:
        results = _first_per_document(
            store.search(
                query_embedding,
                user_id=GOLDEN_USER,
                top_k=top_k * OVERFETCH_FACTOR,
            ),
            top_k,
        )
    else:
        results = []
        for mode in (DATE_MATCH_IN_RANGE, DATE_MATCH_UNDATED, DATE_MATCH_OUT_OF_RANGE):
            if len(results) >= top_k:
                break
            shortfall = top_k - len(results)
            tier = _first_per_document(
                store.search(
                    query_embedding,
                    user_id=GOLDEN_USER,
                    top_k=shortfall * OVERFETCH_FACTOR,
                    date_from=date_from,
                    date_to=date_to,
                    date_mode=mode,
                ),
                shortfall,
            )
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
