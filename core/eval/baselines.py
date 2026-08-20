from __future__ import annotations

import time
from pathlib import Path

from core.eval.runner import (
    EVAL_USER_ID,
    QueryResult,
    get_document_filename_map,
    load_golden,
    score_retrieved,
)

_TS_STOPWORDS = frozenset({
    "the", "and", "for", "are", "was", "does", "did", "how", "what", "why",
    "who", "which", "with", "from", "into", "that", "this", "those", "these",
    "its", "it", "is", "of", "in", "on", "to", "a", "an", "at", "by", "as",
})


def _or_tsquery(query_text: str) -> str:
    """Build an OR-joined tsquery from free text.

    Deliberately NOT `websearch_to_tsquery`/`plainto_tsquery`: both AND the
    terms together, so a chunk must contain *every* word of a
    natural-language question to match at all. Measured on this corpus that
    returned **zero documents for 24 of 45 golden queries** (median documents
    matched: 0), which would understate the keyword baseline for a structural
    reason rather than a retrieval one — flattering the semantic numbers it
    is supposed to challenge.

    Keyword ranking is meant to score partial overlap: match any term, rank
    by how well the document matches overall. Hence `|`.
    """
    terms = []
    for raw in query_text.lower().replace("-", " ").split():
        token = "".join(ch for ch in raw if ch.isalnum())
        if len(token) > 2 and token not in _TS_STOPWORDS:
            terms.append(token)
    return " | ".join(terms)


def bm25_search(
    query_text: str, user_id: str = EVAL_USER_ID, top_k: int = 10
) -> tuple[list[str], float]:
    """Rank documents by Postgres full-text search over `chunks.text`.

    This is the classic IR baseline (Phase 1.4 / docs/plan.md): keyword
    ranking via `to_tsvector` / `ts_rank` / `websearch_to_tsquery`. It needs
    no new dependency and no re-indexing of embeddings — it runs against the
    exact same `chunks` table the semantic path already uses.

    Each document's score is the best (MAX) `ts_rank` among its chunks, so
    the query aggregates straight to document level, ranked descending —
    already deduplicated and directly comparable to the deduped semantic
    ranking `run_eval` produces (see `runner.score_retrieved`).

    Returns (ranked_document_ids, latency_ms). A query with no keyword
    overlap at all (e.g. a purely temporal expression that fully strips to
    an empty string) returns no rows rather than raising.
    """
    from core.index import get_vector_store

    tsquery = _or_tsquery(query_text)
    if not tsquery:
        return [], 0.0

    start = time.perf_counter()
    store = get_vector_store()
    conn = store._connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT document_id,
                       MAX(ts_rank(to_tsvector('english', text),
                                   to_tsquery('english', %s))) AS score
                FROM chunks
                WHERE user_id = %s
                  AND to_tsvector('english', text) @@ to_tsquery('english', %s)
                GROUP BY document_id
                ORDER BY score DESC
                LIMIT %s
                """,
                (tsquery, user_id, tsquery, top_k),
            )
            rows = cur.fetchall()
    finally:
        store._release(conn)

    elapsed_ms = (time.perf_counter() - start) * 1000
    return [r[0] for r in rows], elapsed_ms


def run_eval_bm25(
    golden_path: Path, top_k: int = 10, user_id: str = EVAL_USER_ID
) -> list[QueryResult]:
    """BM25 counterpart to `runner.run_eval` — same queries, same scoring,
    different retriever, so the two are directly comparable.
    """
    from core.query.parser import parse_query

    queries = load_golden(golden_path)
    id_to_filename = get_document_filename_map(user_id)
    results = []

    for q in queries:
        # Mirror what the semantic path does before embedding (see
        # core/api/routes/search.py): strip date expressions out of the
        # query text first. Otherwise a query like "invoices before 2023"
        # leaves "before 2023" in the tsquery, which the semantic side never
        # has to contend with — not an apples-to-apples comparison.
        cleaned_query = parse_query(q.query).query
        retrieved_doc_ids, latency_ms = bm25_search(cleaned_query, user_id, top_k)
        results.append(score_retrieved(q, retrieved_doc_ids, id_to_filename, latency_ms))

    return results
