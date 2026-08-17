from __future__ import annotations

import os

from .pgvector import PgVectorStore


class LocalPgVectorStore(PgVectorStore):
    """Local PostgreSQL with pgvector extension.

    Uses the same SQL interface as Supabase but connects to a local
    PostgreSQL instance (e.g. Docker or native install).
    """

    def __init__(self, connection_string: str | None = None):
        cs = connection_string or os.environ.get(
            "QUERYNEST_DATABASE_URL",
            "postgresql://querynest:querynest@localhost:5432/querynest",
        )
        super().__init__(connection_string=cs)
