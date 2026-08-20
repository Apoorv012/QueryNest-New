from __future__ import annotations

import os

from .local import LocalPgVectorStore
from .pgvector import PgVectorStore

_cached_store: PgVectorStore | LocalPgVectorStore | None = None


def get_vector_store() -> PgVectorStore | LocalPgVectorStore:
    global _cached_store
    if _cached_store is None:
        mode = os.environ.get("QUERYNEST_STORAGE_MODE", "supabase")
        _cached_store = LocalPgVectorStore() if mode == "local" else PgVectorStore()
    return _cached_store
