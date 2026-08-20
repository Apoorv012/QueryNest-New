from __future__ import annotations

import os
from datetime import date
from typing import TYPE_CHECKING

import numpy as np

from .base import DocumentInfo, SearchResult, SourceBlock, VectorStore

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
        self._pool = None

    def _get_pool(self):
        if self._pool is None:
            from psycopg2.pool import ThreadedConnectionPool
            self._pool = ThreadedConnectionPool(1, 5, self._cs)
        return self._pool

    def _connect(self) -> psycopg2.extensions.connection:
        return self._get_pool().getconn()

    def _release(self, conn: psycopg2.extensions.connection) -> None:
        if self._pool is not None:
            self._pool.putconn(conn)

    def setup(self) -> None:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS chunks (
                        id              SERIAL PRIMARY KEY,
                        document_id     TEXT NOT NULL,
                        user_id         TEXT NOT NULL DEFAULT 'default',
                        filename        TEXT NOT NULL DEFAULT '',
                        chunk_index     INTEGER NOT NULL,
                        text            TEXT NOT NULL,
                        heading         TEXT NOT NULL DEFAULT '',
                        embedding       vector(384) NOT NULL,
                        page            INTEGER NOT NULL DEFAULT 0,
                        document_date   DATE,
                        created_at      TIMESTAMP DEFAULT NOW()
                    )
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_chunks_embedding
                    ON chunks USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_chunks_user_id
                    ON chunks (user_id)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_chunks_document_date
                    ON chunks (document_date)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_chunks_document_id
                    ON chunks (document_id)
                """)
                cur.execute("""
                    ALTER TABLE chunks ADD COLUMN IF NOT EXISTS source_blocks JSONB
                """)
            conn.commit()
        finally:
            self._release(conn)

    def store_chunks(
        self,
        document_id: str,
        user_id: str,
        filename: str,
        texts: list[str],
        embeddings: np.ndarray,
        headings: list[str],
        pages: list[int],
        chunk_indices: list[int],
        document_date: date | None = None,
        source_blocks: list[list[dict]] | None = None,
    ) -> None:
        import json
        conn = self._connect()
        try:
            from psycopg2.extras import execute_values
            with conn.cursor() as cur:
                rows = []
                for i, text in enumerate(texts):
                    vec_str = "[" + ",".join(f"{v:.6f}" for v in embeddings[i]) + "]"
                    sb_json = json.dumps(source_blocks[i]) if source_blocks else None
                    rows.append((
                        document_id,
                        user_id,
                        filename,
                        chunk_indices[i],
                        text,
                        headings[i],
                        vec_str,
                        pages[i],
                        document_date,
                        sb_json,
                    ))
                execute_values(
                    cur,
                    """
                    INSERT INTO chunks
                        (document_id, user_id, filename, chunk_index, text, heading,
                         embedding, page, document_date, source_blocks)
                    VALUES %s
                    """,
                    rows,
                    template=None,
                    page_size=100,
                )
            conn.commit()
        finally:
            self._release(conn)

    def search(
        self,
        query_embedding: np.ndarray,
        user_id: str,
        top_k: int = 5,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[SearchResult]:
        conn = self._connect()
        try:
            from psycopg2 import sql

            vec_str = "[" + ",".join(f"{v:.6f}" for v in query_embedding) + "]"

            conditions = [sql.SQL("user_id = %s")]
            params: list = [user_id]

            if date_from is not None:
                conditions.append(sql.SQL("(document_date IS NULL OR document_date >= %s)"))
                params.append(date_from)
            if date_to is not None:
                conditions.append(sql.SQL("(document_date IS NULL OR document_date <= %s)"))
                params.append(date_to)

            where = sql.SQL(" AND ").join(conditions)

            query = sql.SQL(
                """
                SELECT id, document_id, text, heading, page, document_date,
                       source_blocks,
                       1 - (embedding <=> %s::vector) AS score
                FROM chunks
                WHERE {where}
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """
            ).format(where=where)

            with conn.cursor() as cur:
                cur.execute(query, [vec_str, *params, vec_str, top_k])
                import json
                results = []
                for row in cur.fetchall():
                    raw_sb = row[6]
                    sb_list = []
                    if raw_sb:
                        sb_data = raw_sb if isinstance(raw_sb, list) else json.loads(raw_sb)
                        for sb in sb_data:
                            sb_list.append(SourceBlock(
                                text=sb["text"],
                                page=sb["page"],
                                bbox=sb["bbox"],
                                type=sb["type"],
                            ))
                    results.append(SearchResult(
                        chunk_id=row[0],
                        document_id=row[1],
                        text=row[2],
                        heading=row[3],
                        score=float(row[7]),
                        page=row[4],
                        document_date=row[5],
                        source_blocks=sb_list,
                    ))
                return results
        finally:
            self._release(conn)

    def list_documents(self, user_id: str) -> list[DocumentInfo]:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT document_id, filename, document_date, COUNT(*) as chunk_count
                    FROM chunks
                    WHERE user_id = %s
                    GROUP BY document_id, filename, document_date
                    ORDER BY MIN(created_at) DESC
                    """,
                    (user_id,),
                )
                return [
                    DocumentInfo(
                        document_id=row[0],
                        filename=row[1],
                        user_id=user_id,
                        document_date=row[2],
                        chunk_count=row[3],
                    )
                    for row in cur.fetchall()
                ]
        finally:
            self._release(conn)

    def update_document_date(
        self, document_id: str, user_id: str, document_date: date | None
    ) -> None:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE chunks SET document_date = %s
                    WHERE document_id = %s AND user_id = %s
                    """,
                    (document_date, document_id, user_id),
                )
            conn.commit()
        finally:
            self._release(conn)

    def delete_document(self, document_id: str, user_id: str) -> None:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM chunks WHERE document_id = %s AND user_id = %s",
                    (document_id, user_id),
                )
            conn.commit()
        finally:
            self._release(conn)

    def delete_all_for_user(self, user_id: str) -> int:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM chunks WHERE user_id = %s",
                    (user_id,),
                )
                deleted = cur.rowcount
            conn.commit()
            return deleted
        finally:
            self._release(conn)

    def close(self) -> None:
        if self._pool is not None:
            self._pool.closeall()
            self._pool = None
