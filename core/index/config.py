from __future__ import annotations

import os

from .local import LocalPgVectorStore
from .pgvector import PgVectorStore


def get_vector_store() -> PgVectorStore | LocalPgVectorStore:
    mode = os.environ.get("QUERYNEST_STORAGE_MODE", "supabase")
    if mode == "local":
        return LocalPgVectorStore()
    return PgVectorStore()
