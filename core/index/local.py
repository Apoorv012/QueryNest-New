from __future__ import annotations

import os

from .pgvector import PgVectorStore

LOCAL_DATABASE_URL_VAR = "QUERYNEST_LOCAL_DATABASE_URL"


class LocalPgVectorStore(PgVectorStore):
    """Local PostgreSQL with pgvector extension.

    Uses the same SQL interface as Supabase but connects to a local
    PostgreSQL instance (e.g. Docker or native install).

    Reads its connection string from QUERYNEST_LOCAL_DATABASE_URL only. It
    deliberately does NOT fall back to QUERYNEST_DATABASE_URL: that variable
    holds the hosted/Supabase string, and falling back to it meant setting
    QUERYNEST_STORAGE_MODE=local silently connected to production instead.
    """

    def __init__(self, connection_string: str | None = None):
        cs = connection_string or os.environ.get(LOCAL_DATABASE_URL_VAR)
        if not cs:
            raise RuntimeError(
                f"{LOCAL_DATABASE_URL_VAR} not set. "
                "Set it to your local Postgres connection string, e.g. "
                "postgresql://querynest:querynest@localhost:5432/querynest"
            )
        super().__init__(connection_string=cs)
