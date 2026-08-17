from __future__ import annotations

import os
from typing import TYPE_CHECKING

import numpy as np

from .base import SearchResult, VectorStore

if TYPE_CHECKING:
    import psycopg2.extensions


def _get_connection_string() -> str:
    cs = os.environ.get("QUERYNEST_DATABASE_URL")
    if cs:
        return cs
    raise RuntimeError(
        "QUERYNEST_DATABASE_URL not set. "
        "Set it to your Supabase Postgres connection string."
    )


class PgVectorStore(VectorStore):
    def __init__(self, connection_string: str | None = None):
        self._cs = connection_string or _get_connection_string()
        self._conn: psycopg2.extensions.connection | None = None

    def _connect(self) -> psycopg2.extensions.connection:
        if self._conn is None or self._conn.closed:
            import psycopg2
            self._conn = psycopg2.connect(self._cs)
        return self._conn

    def setup(self) -> None:
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id            SERIAL PRIMARY KEY,
                    document_id   TEXT NOT NULL,
                    chunk_index   INTEGER NOT NULL,
                    text          TEXT NOT NULL,
                    heading       TEXT NOT NULL DEFAULT '',
                    embedding     vector(384) NOT NULL,
                    page          INTEGER NOT NULL DEFAULT 0,
                    created_at    TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunks_embedding
                ON chunks USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunks_document_id
                ON chunks (document_id)
            """)
        conn.commit()

    def store_chunks(
        self,
        document_id: str,
        texts: list[str],
        embeddings: np.ndarray,
        headings: list[str],
        pages: list[int],
        chunk_indices: list[int],
    ) -> None:
        conn = self._connect()
        with conn.cursor() as cur:
            for i, text in enumerate(texts):
                vec_str = "[" + ",".join(f"{v:.6f}" for v in embeddings[i]) + "]"
                cur.execute(
                    """
                    INSERT INTO chunks (document_id, chunk_index, text, heading, embedding, page)
                    VALUES (%s, %s, %s, %s, %s::vector, %s)
                    """,
                    (document_id, chunk_indices[i], text, headings[i], vec_str, pages[i]),
                )
        conn.commit()

    def search(
        self, query_embedding: np.ndarray, top_k: int = 5, score_threshold: float = 0.0
    ) -> list[SearchResult]:
        conn = self._connect()
        vec_str = "[" + ",".join(f"{v:.6f}" for v in query_embedding) + "]"
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, document_id, text, heading, page,
                       1 - (embedding <=> %s::vector) AS score
                FROM chunks
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (vec_str, vec_str, top_k),
            )
            results = []
            for row in cur.fetchall():
                score = float(row[5])
                if score >= score_threshold:
                    results.append(SearchResult(
                        chunk_id=row[0],
                        document_id=row[1],
                        text=row[2],
                        heading=row[3],
                        score=score,
                        page=row[4],
                    ))
            return results

    def delete_document(self, document_id: str) -> None:
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chunks WHERE document_id = %s", (document_id,))
        conn.commit()

    def close(self) -> None:
        if self._conn and not self._conn.closed:
            self._conn.close()
            self._conn = None
