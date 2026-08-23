# QueryNest — Architecture Guide

Technical reference for contributors and anyone who wants to understand how the system works.

---

## Overview

QueryNest transforms raw PDFs into searchable, semantically indexed chunks. The system has two layers:

1. **Core Engine** (Python): PDF extraction, chunking, embedding, vector search
2. **Frontend Clients**: Desktop app, mobile apps, web app

---

## Current Pipeline

```
PDF → pymupdf4llm → ExtractedDocument → chunker → List[Chunk] → fastembed → VectorStore
```

### Stage 1: Extraction

**Module**: `core/ingest/extractor.py`

Uses pymupdf4llm to extract text with layout awareness:

- Multi-column reading order reconstruction
- Heading detection via font-size hierarchy
- Table, image, and formula detection
- Bounding boxes for every text block
- Page-level organization

**Input**: PDF file path
**Output**: `ExtractedDocument` containing `ExtractedPage`s containing `ExtractedBlock`s

### Stage 2: Chunking

**Module**: `core/chunking/chunker.py`

Groups consecutive blocks into semantically coherent chunks:

- **Trigger 1**: Heading boundary (when `section-header` block encountered)
- **Trigger 2**: Token overflow (MAX_TOKENS = 400)
- **Minimum**: MIN_TOKENS = 120 (prevents tiny chunks mid-document)
- **Post-filter**: chunks below `DROP_BELOW_TOKENS = 20` are discarded after chunking (a
  heading immediately followed by another heading emits a chunk containing only the first
  heading's text). If every chunk in a document is below the threshold, the document is kept
  as-is rather than emptied. See D13 in `docs/decisions.md`.
- **Token estimation**: `word_count × 1.3` (rough heuristic)

**Input**: `ExtractedDocument`
**Output**: `List[Chunk]`

### Stage 3: Embedding

**Module**: `core/embedding/`

Turns chunk text into dense vectors for semantic search:

- `base.py`: `BaseEmbedder` ABC — `embed(texts, batch_size) -> np.ndarray`, `embed_query(query) -> np.ndarray`, `embedding_dim` property.
- `fastembed.py`: `FastEmbedEmbedder` implementation, wrapping fastembed's `TextEmbedding` (ONNX Runtime). Uses `BAAI/bge-small-en-v1.5` (384 dims) by default. `get_instance()` returns a process-wide cached singleton so the ONNX model is only loaded once.

**Input**: `List[str]` (chunk texts, or a single query string)
**Output**: `np.ndarray` of shape `(n_texts, 384)`, or `(384,)` for a single query

### Stage 4: Indexing

**Module**: `core/index/`

Persists embedded chunks and serves vector search:

- `base.py`: `VectorStore` ABC defining the storage contract — `setup()`, `store_chunks(...)`, `find_by_content_hash(user_id, content_hash) -> str | None`, `search(query_embedding, user_id, top_k, date_from, date_to, date_mode) -> list[SearchResult]`, `list_documents(user_id) -> list[DocumentInfo]`, `update_document_date(document_id, user_id, document_date)`, `delete_document(document_id, user_id)`, `delete_all_for_user(user_id) -> int`, `close()`.
- `pgvector.py`: `PgVectorStore` — Supabase/hosted Postgres implementation. Owns two tables: `documents` (one row per document — `user_id`, `filename`, `document_date`, `content_hash`, `page_count`, `chunk_count`) and `chunks` (one row per chunk — `document_id` FK, `chunk_index`, `text`, `heading`, `embedding`, `page`, `source_blocks`). `setup()` runs an idempotent, re-runnable migration (`_migrate_document_metadata`) that backfills `documents` from any pre-existing `chunks` rows before dropping the now-duplicated `user_id`/`filename`/`document_date` columns off `chunks`. See D14 in `docs/decisions.md`.
- `local.py`: `LocalPgVectorStore` — local Postgres implementation; subclasses `PgVectorStore` and overrides only the connection string, so it shares the same schema, migration, and dedup logic. Reads its connection string exclusively from `QUERYNEST_LOCAL_DATABASE_URL` (not `QUERYNEST_DATABASE_URL`), so the two storage modes can never accidentally share credentials.
- `config.py`: `get_vector_store()` returns a cached singleton, picking `LocalPgVectorStore` or `PgVectorStore` based on `QUERYNEST_STORAGE_MODE` (`local` vs. default `supabase`). Also exposes `get_storage_mode() -> str` (reads `QUERYNEST_STORAGE_MODE`, defaulting to `"supabase"`) and `is_store_configured() -> bool`, which checks whether the connection-string variable for the *current* mode is set (`QUERYNEST_LOCAL_DATABASE_URL` for `local`, `QUERYNEST_DATABASE_URL` otherwise) — checking `QUERYNEST_DATABASE_URL` alone would wrongly report "no database" while running in local mode.

**Input**: chunk texts, embeddings, and metadata (headings, pages, chunk indices, document date, source blocks, content hash, page count)
**Output**: stored rows; `search()` returns ranked `SearchResult`s, optionally pre-filtered by a `[date_from, date_to]` range on `document_date` and a `date_mode` tier (see D12 below).

**Content-hash dedup (D14).** `POST /upload/bulk` (`core/api/routes/upload.py`) SHA-256-hashes
each file's bytes before extraction and calls `find_by_content_hash(user_id, content_hash)`.
On a hit, it short-circuits to the existing `document_id` and reports the file as
`was_duplicate: true` instead of re-extracting, re-chunking, and re-embedding — extraction is
~77% of ingest cost, so this removes that work entirely on a re-upload rather than rearranging
it. `documents (user_id, content_hash)` carries a partial unique index (`WHERE content_hash IS
NOT NULL`), since documents ingested before hashing existed have no hash to enforce against.

**Date filtering is three-tiered, not a boolean (D12).** `SearchResult` does not carry a
`within_date_range` flag — it carries `date_match: str`, one of four values defined in
`core/index/base.py`:

| `date_match` | Meaning |
|---|---|
| `in_range` | Document has a date, and it falls inside the requested range |
| `undated` | Document has no detectable date — it *might* match |
| `out_of_range` | Document has a date, and it falls outside the requested range |
| `unfiltered` | No date filter was applied to this search at all |

When a query carries a date filter, `core/api/routes/search.py` queries the store tier by tier
(`in_range` → `undated` → `out_of_range`), each call asking only for the shortfall needed to
reach `top_k`, stopping as soon as `top_k` is met. The route stamps `date_match` on each result
itself rather than trusting the store to do it, so the label can't drift between store
implementations. Tier order beats similarity score deliberately — a high-scoring out-of-range
document ranks below a lower-scoring in-range one. See D12 in `docs/decisions.md` for the full
rationale (undated documents rank above known-wrong ones because "unknown" and "known wrong" are
different confidence levels, not the same non-match).

### Stage 4b: File Storage

**Module**: `core/storage/`

Persists uploaded PDF bytes, independent of the vector store, with the same local/hosted split:

- `base.py`: `FileStore` ABC — `save(user_id, doc_id, data)`, `get(user_id, doc_id) -> bytes | str` (raw bytes locally, a signed URL when hosted), `delete(user_id, doc_id)`, `delete_all(user_id)`.
- `local.py`: `LocalFileStore` — writes to `data/uploads/{user_id}/{doc_id}.pdf`, same layout the API used before this abstraction existed.
- `supabase.py`: `SupabaseFileStore` — calls the Supabase Storage REST API directly via `requests` (upload, generate a signed URL, delete/list-and-delete for `delete_all`). No `supabase-py` SDK dependency.
- `config.py`: `get_file_store()` — cached singleton, picks the implementation off `QUERYNEST_STORAGE_MODE` (same env var `core/index/config.py` uses for the database, so the two storage layers always agree on local vs. hosted).

**Why it exists**: `core/api/routes/upload.py` and `documents.py` used to call `Path.write_bytes()`/`FileResponse` directly, which works locally but not on Render, whose filesystem is ephemeral. See D16 in `docs/decisions.md`.

### Stage 5: Query Parsing

**Module**: `core/query/parser.py`

Regex-based extraction of natural-language date expressions from a raw search query, so hybrid search can combine a semantic query with a SQL date filter in one store call:

- Recognizes relative ranges ("last 3 years", "past 6 months", "last year"), exact years ("in 2020"), inclusive ranges ("from 2020 to 2023", "2020-2023"), and open-ended bounds ("before 2020", "after 2020").
- `parse_query(query) -> ParsedQuery`, where `ParsedQuery` holds the date-expression-stripped `query` text plus optional `date_from`/`date_to`.

**Input**: raw query string (e.g. `"encoder architecture from 2020 to 2023"`)
**Output**: `ParsedQuery(query="encoder architecture", date_from=date(2020,1,1), date_to=date(2023,12,31))`

---

## Data Models

### ExtractedBlock

One span of text from a PDF.

| Field | Type | Description |
|---|---|---|
| `text` | `str` | Extracted text content |
| `page` | `int` | Zero-indexed page number |
| `bbox` | `Tuple[float, float, float, float]` | Bounding box `(x0, y0, x1, y1)` in PDF points |
| `type` | `str` | Block type: "text", "section-header", "table", "caption", etc. |

### ExtractedPage

A single page from the PDF.

| Field | Type | Description |
|---|---|---|
| `page_number` | `int` | Zero-indexed page number |
| `blocks` | `List[ExtractedBlock]` | All blocks on this page |

### ExtractedDocument

The complete extracted document.

| Field | Type | Description |
|---|---|---|
| `filename` | `str` | Original PDF filename |
| `pages` | `List[ExtractedPage]` | All pages in order |

### Chunk

A semantically coherent unit of text, ready for embedding.

| Field | Type | Description |
|---|---|---|
| `text` | `str` | Joined paragraph text |
| `source_blocks` | `List[ExtractedBlock]` | Original blocks that make up this chunk |
| `heading` | `str` | Section heading (from `section-header` blocks) |
| `chunk_index` | `int` | Sequential index within document |

### SourceBlock / SearchResult / DocumentInfo

Index-layer types (`core/index/base.py`), distinct from the ingestion-layer models above — these are what `VectorStore.search()` and `VectorStore.list_documents()` return.

**SourceBlock** — a trimmed-down copy of `ExtractedBlock` stored alongside a chunk for highlight rendering.

| Field | Type | Description |
|---|---|---|
| `text` | `str` | Block text |
| `page` | `int` | Zero-indexed page number |
| `bbox` | `list[float]` | Bounding box |
| `type` | `str` | Block type |

**SearchResult** — one ranked search hit.

| Field | Type | Description |
|---|---|---|
| `chunk_id` | `int` | Store-assigned chunk id |
| `document_id` | `str` | Owning document id |
| `filename` | `str` | Owning document's original filename (joined from `documents`, default `""`) |
| `text` | `str` | Chunk text |
| `heading` | `str` | Section heading |
| `score` | `float` | Similarity score |
| `page` | `int` | Page of the chunk's first block |
| `document_date` | `date \| None` | Resolved document date |
| `source_blocks` | `list[SourceBlock]` | Blocks making up the chunk |
| `date_match` | `str` | D12 tier: `"in_range"`, `"undated"`, `"out_of_range"`, or `"unfiltered"` (default) |

**DocumentInfo** — one row in a document listing.

| Field | Type | Description |
|---|---|---|
| `document_id` | `str` | Document id |
| `filename` | `str` | Original filename |
| `user_id` | `str` | Owning user |
| `document_date` | `date \| None` | Resolved document date |
| `chunk_count` | `int` | Number of chunks stored for the document |

These are backed by two tables now, not one — see D14. `document_id`, `filename`, `user_id`,
and `document_date` live on `documents`; `chunk_count` and `page_count` are also tracked there
(denormalized at write time) so listing documents never needs to scan `chunks`.

---

## Module Details

### core/ingest/

- `extractor.py`: Single function `extract(pdf_path) -> ExtractedDocument`. Wraps pymupdf4llm JSON output.
- `date_extractor.py`: `extract_date(filename, pdf_metadata, first_page_text) -> tuple[date | None, str | None]`. Resolves a document date via the D5 fallback chain (filename → PDF metadata → content), returning the date plus which source it came from (`"filename"`, `"metadata"`, `"content"`, or `None`). Also exposes the individual `extract_date_from_filename`, `extract_date_from_metadata`, `extract_date_from_text` helpers.

### core/chunking/

- `chunker.py`: `chunk_document(doc) -> List[Chunk]`. Groups blocks by heading, flushes on boundary or overflow, then drops chunks below `DROP_BELOW_TOKENS` (D13).
- `tokenizer.py`: `estimate_tokens(text) -> int`. Rough word-count-based estimate.

### core/embedding/

- `base.py`: `BaseEmbedder` ABC.
- `fastembed.py`: `FastEmbedEmbedder`, cached singleton via `get_instance()`.

### core/index/

- `base.py`: `VectorStore` ABC, `SourceBlock`, `SearchResult`, `DocumentInfo`.
- `pgvector.py`: `PgVectorStore` (Supabase/hosted Postgres); `documents` + `chunks` schema, content-hash dedup, metadata migration (D14).
- `local.py`: `LocalPgVectorStore` (local Postgres, same schema, inherited from `PgVectorStore`).
- `config.py`: `get_vector_store()` — picks an implementation from `QUERYNEST_STORAGE_MODE` and caches it.

### core/query/

- `parser.py`: `parse_query(query) -> ParsedQuery`. Regex-based NL date-range extraction (see Stage 5 above).

### core/models/

- `extracted.py`: `ExtractedBlock`, `ExtractedPage`, `ExtractedDocument`
- `chunk.py`: `Chunk`

### core/eval/

Golden-query-set retrieval evaluation. See `docs/evaluation.md` for full methodology.

- `runner.py`: `load_golden(path) -> list[EvalQuery]` parses the golden dataset; `run_search(query_text, top_k)` calls `POST /api/search` on a running API instance (`DEFAULT_API_URL = "http://127.0.0.1:8000"` — use `127.0.0.1`, not `localhost`; on Windows, `localhost` resolves via IPv6 first and adds ~2s of latency per request); `run_eval(golden_path, top_k) -> list[QueryResult]` runs every golden query and computes precision@{5,10}, recall@{5,10}, nDCG@10, and MRR per query; `get_git_commit()` returns the short git hash for tagging reports.
- `metrics.py`: `precision_at_k`, `recall_at_k`, `ndcg_at_k`, `mrr` — pure functions over retrieved/relevant id lists.
- `baselines.py`: BM25 keyword baseline (Phase 1.4/D-series) via Postgres full-text search (`to_tsvector`/`ts_rank`/`to_tsquery`) over `chunks.text` — no new dependency, same table the semantic path uses. `bm25_search(query_text, ...)` ranks documents by best per-chunk `ts_rank`, joining `chunks` to `documents` for `user_id` (moved off `chunks` by D14); `run_eval_bm25(golden_path, ...)` is the BM25 counterpart to `runner.run_eval`, same scoring, so the two are directly comparable. Query terms are OR-joined (not AND, which returned zero documents for over half the golden queries in testing) and date expressions are stripped via `core.query.parser.parse_query` first, mirroring what the semantic path does before embedding.
- `report.py`: `print_report(results)` prints a console summary; `generate_report(results, output_dir)` writes a timestamped, git-commit-tagged JSON report (aggregate metrics, by-type breakdown, worst queries by MRR, per-query results) to `reports/`.
- `download_pdfs.py`: Fetches the fixture PDFs used by the golden dataset into `data/eval/pdfs/<category>/`.
- `__main__.py`: `python -m core.eval` — runs `run_eval` against `data/eval/golden.json`, prints the report, and saves it to `reports/`.

**Two golden query sets exist** in `data/eval/`: `golden.json` (the primary set) and
`golden_paraphrased.json` (the same queries reworded, used to check whether retrieval quality
holds up under phrasing variation rather than being tuned to one exact wording).

### core/api/ — Full Backend (`main.py`, Local Admin Only, Never Deployed)

- `main.py`: FastAPI app; CORS for `localhost:5173`; lifespan hook calls `store.setup()` when `QUERYNEST_DATABASE_URL` is set, otherwise runs in-memory-only.
- `routes/`: route modules, assembled in `routes/__init__.py` as `api_router`.
  - `health.py`: `GET /`, `GET /health`, `GET /check-backend` (identical payload to `/health`, under a name ad-blockers don't filter — see the public API section below).
  - `upload.py`: `POST /upload/bulk` (background bulk upload — hashes each file and short-circuits to the existing document on a content-hash match (D14); otherwise extracts, chunks, date-detects, and, when a database is configured, embeds and stores the file via `core/storage`), `GET /upload/{job_id}/status` (per-file job progress, including `was_duplicate`)
  - `documents.py`: `GET /documents`, `GET /documents/{doc_id}/chunks`, `PATCH /documents/{doc_id}/date`, `GET /documents/{doc_id}/pdf` (`?download=true` for `Content-Disposition: attachment`)
  - `search.py`: `POST /search` — parses NL date expressions out of the query, embeds the remaining text, and runs a hybrid (semantic + date-filtered) store search
  - `eval.py`: `POST /eval/seed` (background job that re-indexes the eval fixture PDFs for a dedicated `golden_user`, via `core.api.constants.GOLDEN_USER`), `GET /eval/seed/{job_id}/status` — this is how the public demo's corpus is (re)seeded, always run locally against the same Supabase project the public backend reads from.
- `constants.py`: `GOLDEN_USER = "golden_user"`, shared by `eval.py` and the public routes below.
- `jobs.py`: Thread-safe in-process `Job`/`FileStatus` tracker for background bulk-upload and eval-seed progress (not persisted, not for production scale).
- `store.py`: In-memory chunk store used by the chunk-viewer dev tool (separate from the vector store).

### core/api/ — Lite Public Backend (`public_main.py`, Deployed to Render)

A second, independent `FastAPI()` instance — not the app above with routes disabled. It imports
only three routers, so upload/eval/mutation are structurally absent, not merely unauthenticated.
See D15 in `docs/decisions.md`.

- `public_main.py`: own lifespan (just `store.setup()`), CORS restricted to `QUERYNEST_DEMO_ORIGIN` (comma-separated, no `localhost`, no wildcard).
- `routes/public_search.py`: `POST /search` — request body has no `user_id` field at all; always searches `GOLDEN_USER` server-side. Reuses `search.py`'s `_first_per_document`/`OVERFETCH_FACTOR` tiered-search logic by import. Wrapped in a small in-memory fixed-window IP rate limiter, since this route is fully public with zero auth.
- `routes/public_documents.py`: `GET /documents` (read-only golden-corpus listing, no `user_id` param), `GET /documents/{doc_id}/pdf` (read-only, `GOLDEN_USER`-scoped, `?download=true` supported).
- `routes/health.py`'s `GET /health` and `GET /check-backend` are shared with the full backend (same file, same router).

### apps/demo/ — Public Frontend (Deployed to Vercel)

React + TypeScript + Vite, cloned from `tools/dev-dashboard`'s component structure rather than
built fresh, then adapted for public consumption:

- Two static pages via Vite's native multi-page build (no router dependency): `index.html` (landing/marketing) and `demo/index.html`, served at the `/demo/` route.
- `src/demo/App.tsx` + `components/`: same look as the dev dashboard, but mutation controls (Upload, Seed Golden Set) are rendered `disabled` with a hover tooltip (`components/Disabled.tsx`, `direction="down"` for controls near the top of the page/a clipping ancestor) rather than removed — the demo should look and feel like the real tool, just read-only. The user selector is a locked `golden_user` label, not an editable input.
- `src/demo/lib/api.ts`: talks only to the lite public backend's four routes. `checkBackend()` hits `/check-backend`, not `/health` — ad-blockers (Brave Shields included) commonly filter generic paths like `/health`/`/ping`/`/beacon` as tracking pings, silently failing the request client-side with zero bytes ever sent, which otherwise shows as a false "offline" indicator even though the API is reachable.
- `VITE_API_BASE` env var (build-time) points at the Render backend URL.

### tools/chunk-viewer/ (Dev Only)

React + TypeScript + Vite app for inspecting extraction output. Shows chunk list, source blocks, and metadata.

---

## Production Architecture

### Current Deployment (Live)

```
                    ┌─────────────────────┐
                    │  querynest.apoorvm.com │  (Vercel, CNAME)
                    │  apps/demo — landing + /demo/
                    └──────────┬──────────┘
                               │ VITE_API_BASE
                               ▼
                    ┌─────────────────────┐
  GitHub Actions ──▶│ querynest-public-api.onrender.com │
  (ping /health,    │ core/api/public_main.py            │
   every 10 min)    │ health + public_search + public_documents │
                    └──────────┬──────────┘
                               │ pooler connection (IPv4)
                               ▼
                    ┌─────────────────────┐
                    │   Supabase project    │
                    │   Postgres (pgvector) │
                    │   Storage (pdfs bucket)│
                    └─────────────────────┘
                               ▲
                               │ /eval/seed (admin, local only)
                    ┌─────────────────────┐
                    │  core/api/main.py    │  ← runs on your machine,
                    │  + tools/dev-dashboard │    never deployed
                    └─────────────────────┘
```

- **Frontend**: Vercel, `apps/demo` as root directory, `render.yaml`-free (Vercel auto-detects Vite). Custom domain `querynest.apoorvm.com` via CNAME to `cname.vercel-dns.com`.
- **Backend**: Render, Dockerfile-based web service, config in `render.yaml` at repo root. Free tier spins down after ~15 min idle; `.github/workflows/keepalive.yml` pings `/health` every 10 minutes to prevent that (best-effort, not a hard guarantee — GitHub's cron scheduler isn't exact).
- **Database connection gotcha**: Supabase's direct `db.<ref>.supabase.co` host is IPv6-only. Docker Desktop (and Render, and most PaaS) have no IPv6 route by default, so `QUERYNEST_DATABASE_URL` in any deployed/containerized context **must** be the connection **pooler** string (`aws-0-<region>.pooler.supabase.com:6543`), not the direct host — confirmed by reproducing `Network is unreachable` locally in Docker before it would have surfaced in production.
- **The golden corpus lives only in Supabase now** — DB rows and PDF files both. Re-seeding (`POST /eval/seed`, run locally against the full backend) wipes and rewrites both `documents`/`chunks` tables and the `pdfs` Storage bucket for `golden_user`; it never touches other users' data.

### Platform Strategy (Future Scope — Desktop/Mobile)

| Platform | Account | Processing | Offline | Backend |
|---|---|---|---|---|
| Windows | Optional | Local | Yes | Local Postgres or Supabase |
| macOS | Optional | Local | Yes | Local Postgres or Supabase |
| Android | Yes | Cloud | No | Supabase |
| iOS | Yes | Cloud | No | Supabase |
| Web | Yes | Cloud | No | Supabase |

### Storage Strategy (D2)

**Primary**: pgvector in Supabase Postgres

- Vectors stored as `vector` column alongside document/chunk metadata
- **HNSW index** (`USING hnsw (embedding vector_cosine_ops)`) for approximate nearest neighbor
  search — not IVFFlat. IVFFlat learns its cluster centroids from the rows present at
  index-build time, and `setup()` runs against an empty table; the resulting index was
  degenerate (queries returned zero rows at the default `ivfflat.probes = 1`). HNSW builds
  incrementally as rows are inserted and cannot reach that state. See **D11** in
  `docs/decisions.md`.
- SQL WHERE clauses for metadata filtering (year, subject, type)
- Row-level security for user isolation

**Local Mode** (Desktop only):
- PostgreSQL with pgvector extension running locally
- Same schema as Supabase for consistency
- Connection string comes exclusively from `QUERYNEST_LOCAL_DATABASE_URL`, kept separate from
  the Supabase-mode `QUERYNEST_DATABASE_URL` (see `core/index/config.py` above)
- Optional sync to Supabase for mobile access

### Data Flow

```
Desktop Processing:
PDF → Extract → Chunk → Embed → Store in Local Postgres
                                      ↓
                              Sync to Supabase (optional)
                                      ↓
Mobile/Web Access:
Query → Supabase pgvector search → Results → Highlight in PDF viewer
```

---

## Configuration

### Current Constants

```python
# Chunking
MAX_TOKENS = 400
MIN_TOKENS = 120

# Token estimation
TOKEN_RATIO = 1.3  # words × 1.3 ≈ tokens
```

### Planned Configuration

```python
@dataclass
class QueryNestConfig:
    # Embedding
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384

    # Storage
    db_url: str = "postgresql://..."  # Local or Supabase

    # Search
    top_k: int = 10
    similarity_threshold: float = 0.7

    # Highlighting
    highlight_color: Tuple[float, float, float] = (1.0, 1.0, 0.0)  # Yellow
```

---

## Error Handling

- `ValueError`: Invalid input (wrong file type, empty queries)
- `RuntimeError`: Infrastructure failures (PDF load failure, model download)
- All errors include descriptive messages for debugging

---

## Testing

- **Framework**: pytest
- **Fixture**: "Attention Is All You Need" paper (`tests/fixtures/sample.pdf`)
- **Scope**: Session-scoped extraction (runs pymupdf4llm once per test session)
- **Runtime**: ~20 seconds for full suite

```bash
pytest                  # All tests
pytest -v               # Verbose
pytest tests/chunking/  # Chunking tests only
```

---

## Performance

- **Extraction**: ~16 seconds for 15-page PDF (includes ONNX layout analysis)
- **Chunking**: <1 second (pure Python, no I/O)
- **Embedding**: ~100ms per chunk on CPU
- **Search**: <50ms with HNSW index

GPU acceleration available for pymupdf4llm by switching `onnxruntime` to `onnxruntime-gpu` (drop-in replacement, no code changes).

---

## Future Scope

1. **Answer generation**: LLM-based with citations
2. **PDF highlighting**: Syncfusion Flutter PDF Viewer annotations
3. **Offline ↔ online sync**: Desktop syncs with Supabase when online
4. **Cloud processing**: Mobile/web upload to cloud for processing (no desktop required)
