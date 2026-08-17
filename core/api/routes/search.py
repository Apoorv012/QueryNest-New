import os

from fastapi import APIRouter

router = APIRouter()

_has_pgvector = bool(os.environ.get("QUERYNEST_DATABASE_URL"))


@router.post("/search")
def search(query: str = "", top_k: int = 5):
    if not query.strip():
        return {"error": "Query cannot be empty"}

    if not _has_pgvector:
        return {"error": "Search requires database. Set QUERYNEST_DATABASE_URL."}

    from core.embedding import FastEmbedEmbedder
    from core.index import get_vector_store

    embedder = FastEmbedEmbedder()
    query_embedding = embedder.embed_query(query)

    store = get_vector_store()
    results = store.search(query_embedding, top_k=top_k)

    return {
        "query": query,
        "results": [
            {
                "chunk_id": r.chunk_id,
                "document_id": r.document_id,
                "text": r.text,
                "heading": r.heading,
                "score": r.score,
                "page": r.page,
            }
            for r in results
        ],
    }
