from __future__ import annotations

import os
from datetime import date
from typing import TYPE_CHECKING

import numpy as np

from .base import (
    DATE_MATCH_IN_RANGE,
    DATE_MATCH_OUT_OF_RANGE,
    DATE_MATCH_UNDATED,
    DATE_MATCH_UNFILTERED,
    DocumentInfo,
    SearchResult,
    SourceBlock,
    VectorStore,
)

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
                        chunk_index     INTEGER NOT NULL,
                        text            TEXT NOT NULL,
                        heading         TEXT NOT NULL DEFAULT '',
                        embedding       vector(384) NOT NULL,
                        page            INTEGER NOT NULL DEFAULT 0,
                        created_at      TIMESTAMP DEFAULT NOW()
                    )
                """)
                # HNSW, not IVFFlat. IVFFlat learns its centroids from the rows
                # present when the index is built — and setup() runs against an
                # empty table, so the lists were never trained. With the default
                # ivfflat.probes = 1 a query then scans one degenerate list and
                # routinely returns ZERO rows (measured: 0 results by default,
                # 10 with probes=100, 10 on an exact scan). HNSW builds its graph
                # incrementally as rows are inserted, so it needs no training
                # pass and cannot end up in that state.
                cur.execute("DROP INDEX IF EXISTS idx_chunks_embedding")
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw
                    ON chunks USING hnsw (embedding vector_cosine_ops)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_chunks_document_id
                    ON chunks (document_id)
                """)
                cur.execute("""
                    ALTER TABLE chunks ADD COLUMN IF NOT EXISTS source_blocks JSONB
                """)

                cur.execute("""
                    CREATE TABLE IF NOT EXISTS documents (
                        document_id     TEXT PRIMARY KEY,
                        user_id         TEXT NOT NULL,
                        filename        TEXT NOT NULL DEFAULT '',
                        document_date   DATE,
                        content_hash    TEXT,
                        page_count      INTEGER,
                        chunk_count     INTEGER,
                        storage_path    TEXT,
                        created_at      TIMESTAMP DEFAULT NOW()
                    )
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_documents_user_id
                    ON documents (user_id)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_documents_date
                    ON documents (user_id, document_date)
                """)
                # content_hash is nullable and the uniqueness constraint is
                # partial: documents ingested before hashing existed have no
                # hash, and fabricating one would be worse than admitting it.
                # New ingests always set it, so dedup still holds for them.
                cur.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_user_hash
                    ON documents (user_id, content_hash)
                    WHERE content_hash IS NOT NULL
                """)
            conn.commit()
            self._migrate_document_metadata(conn)
        finally:
            self._release(conn)

    def _migrate_document_metadata(self, conn) -> None:
        """Move per-document metadata off `chunks` and onto `documents`.

        `chunks` holds the only copy of user_id/filename/document_date, so the
        backfill must complete before those columns are dropped. Written as an
        explicit, re-runnable step rather than another `setup()` mutation:
        `ADD COLUMN IF NOT EXISTS` is safely idempotent, a column *drop* is not,
        and getting the order wrong loses the metadata irrecoverably.
        """
        with conn.cursor() as cur:
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'chunks' AND column_name = 'user_id'
            """)
            if cur.fetchone() is None:
                return  # already migrated

            # Backfill first. MIN(created_at) keeps the original ingest time;
            # a document's rows all share the same metadata, so MIN over the
            # rest is just "pick the value".
            cur.execute("""
                INSERT INTO documents
                    (document_id, user_id, filename, document_date, chunk_count, created_at)
                SELECT document_id,
                       MIN(user_id),
                       MIN(filename),
                       MIN(document_date),
                       COUNT(*),
                       MIN(created_at)
                FROM chunks
                GROUP BY document_id
                ON CONFLICT (document_id) DO NOTHING
            """)
            migrated = cur.rowcount

            # Only now is it safe to drop the source of truth.
            cur.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS user_id")
            cur.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS filename")
            cur.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS document_date")
            cur.execute("DROP INDEX IF EXISTS idx_chunks_user_id")
            cur.execute("DROP INDEX IF EXISTS idx_chunks_document_date")
        conn.commit()
        if migrated:
            print(f"  migrated {migrated} documents to the documents table")

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
        content_hash: str | None = None,
        page_count: int | None = None,
    ) -> None:
        import json
        conn = self._connect()
        try:
            from psycopg2.extras import execute_values
            with conn.cursor() as cur:
                # The document row must exist before its chunks reference it.
                cur.execute(
                    """
                    INSERT INTO documents (document_id, user_id, filename,
                                           document_date, content_hash,
                                           page_count, chunk_count)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (document_id) DO UPDATE SET
                        filename      = EXCLUDED.filename,
                        document_date = EXCLUDED.document_date,
                        content_hash  = COALESCE(EXCLUDED.content_hash,
                                                 documents.content_hash),
                        page_count    = EXCLUDED.page_count,
                        chunk_count   = EXCLUDED.chunk_count
                    """,
                    (document_id, user_id, filename, document_date,
                     content_hash, page_count, len(texts)),
                )
                rows = []
                for i, text in enumerate(texts):
                    vec_str = "[" + ",".join(f"{v:.6f}" for v in embeddings[i]) + "]"
                    sb_json = json.dumps(source_blocks[i]) if source_blocks else None
                    rows.append((
                        document_id,
                        chunk_indices[i],
                        text,
                        headings[i],
                        vec_str,
                        pages[i],
                        sb_json,
                    ))
                execute_values(
                    cur,
                    """
                    INSERT INTO chunks
                        (document_id, chunk_index, text, heading,
                         embedding, page, source_blocks)
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
        date_mode: str | None = None,
    ) -> list[SearchResult]:
        conn = self._connect()
        try:
            from psycopg2 import sql

            vec_str = "[" + ",".join(f"{v:.6f}" for v in query_embedding) + "]"

            conditions: list[sql.Composable] = [sql.SQL("d.user_id = %s")]
            params: list = [user_id]

            # D12: three mutually exclusive tiers rather than one fuzzy
            # predicate. Because the tiers cannot overlap, results from
            # successive tiers never need de-duplicating against each other.
            if date_mode == DATE_MATCH_UNDATED:
                conditions.append(sql.SQL("d.document_date IS NULL"))
            elif date_mode == DATE_MATCH_IN_RANGE:
                conditions.append(sql.SQL("d.document_date IS NOT NULL"))
                if date_from is not None:
                    conditions.append(sql.SQL("d.document_date >= %s"))
                    params.append(date_from)
                if date_to is not None:
                    conditions.append(sql.SQL("d.document_date <= %s"))
                    params.append(date_to)
            elif date_mode == DATE_MATCH_OUT_OF_RANGE:
                conditions.append(sql.SQL("d.document_date IS NOT NULL"))
                bounds: list[sql.Composable] = []
                if date_from is not None:
                    bounds.append(sql.SQL("d.document_date < %s"))
                    params.append(date_from)
                if date_to is not None:
                    bounds.append(sql.SQL("d.document_date > %s"))
                    params.append(date_to)
                if bounds:
                    conditions.append(
                        sql.SQL("({})").format(sql.SQL(" OR ").join(bounds))
                    )

            where = sql.SQL(" AND ").join(conditions)

            query = sql.SQL(
                """
                SELECT c.id, c.document_id, d.filename, c.text, c.heading, c.page,
                       d.document_date, c.source_blocks,
                       1 - (c.embedding <=> %s::vector) AS score
                FROM chunks c
                JOIN documents d ON d.document_id = c.document_id
                WHERE {where}
                ORDER BY c.embedding <=> %s::vector
                LIMIT %s
                """
            ).format(where=where)

            with conn.cursor() as cur:
                cur.execute(query, [vec_str, *params, vec_str, top_k])
                import json
                results = []
                for row in cur.fetchall():
                    raw_sb = row[7]
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
                        filename=row[2],
                        text=row[3],
                        heading=row[4],
                        score=float(row[8]),
                        page=row[5],
                        document_date=row[6],
                        source_blocks=sb_list,
                        date_match=date_mode or DATE_MATCH_UNFILTERED,
                    ))
                return results
        finally:
            self._release(conn)

    def find_by_content_hash(self, user_id: str, content_hash: str) -> str | None:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT document_id FROM documents
                    WHERE user_id = %s AND content_hash = %s
                    LIMIT 1
                    """,
                    (user_id, content_hash),
                )
                row = cur.fetchone()
                return row[0] if row else None
        finally:
            self._release(conn)

    def list_documents(self, user_id: str) -> list[DocumentInfo]:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT document_id, filename, document_date,
                           COALESCE(chunk_count, 0)
                    FROM documents
                    WHERE user_id = %s
                    ORDER BY created_at DESC
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
                    UPDATE documents SET document_date = %s
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
                    """
                    DELETE FROM chunks WHERE document_id IN (
                        SELECT document_id FROM documents
                        WHERE document_id = %s AND user_id = %s
                    )
                    """,
                    (document_id, user_id),
                )
                cur.execute(
                    "DELETE FROM documents WHERE document_id = %s AND user_id = %s",
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
                    """
                    DELETE FROM chunks WHERE document_id IN (
                        SELECT document_id FROM documents WHERE user_id = %s
                    )
                    """,
                    (user_id,),
                )
                deleted = cur.rowcount
                cur.execute("DELETE FROM documents WHERE user_id = %s", (user_id,))
            conn.commit()
            return deleted
        finally:
            self._release(conn)

    def close(self) -> None:
        if self._pool is not None:
            self._pool.closeall()
            self._pool = None
