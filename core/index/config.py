from __future__ import annotations

import os

from .local import LOCAL_DATABASE_URL_VAR, LocalPgVectorStore
from .pgvector import PgVectorStore

_cached_store: PgVectorStore | LocalPgVectorStore | None = None


def get_storage_mode() -> str:
    return os.environ.get("QUERYNEST_STORAGE_MODE", "supabase")


def is_store_configured() -> bool:
    """Whether a vector store can actually be built for the current mode.

    Each mode has its own connection-string variable, so checking only
    QUERYNEST_DATABASE_URL would report "no database" whenever the app runs
    against local Postgres.
    """
    var = (
        LOCAL_DATABASE_URL_VAR
        if get_storage_mode() == "local"
        else "QUERYNEST_DATABASE_URL"
    )
    return bool(os.environ.get(var))


def get_vector_store() -> PgVectorStore | LocalPgVectorStore:
    global _cached_store
    if _cached_store is None:
        _cached_store = (
            LocalPgVectorStore() if get_storage_mode() == "local" else PgVectorStore()
        )
    return _cached_store
