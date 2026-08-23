# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

QueryNest is an AI-powered semantic search engine for personal PDFs. Users search by meaning, get AI answers with citations, and see highlighted passages in the PDF.

**Current state**: Extraction, chunking, embedding, indexing (pgvector), hybrid search (semantic + NL date filtering), background bulk upload, and an eval framework are implemented. Answer generation with citations and PDF highlight annotation are planned.

**Live public demo**: `querynest.apoorvm.com` — a recruiter-facing, read-only demo searching a fixed `golden_user` corpus (18 PDFs). Frontend on Vercel (`apps/demo`), backend on Render (`core/api/public_main.py`), DB + PDF storage on Supabase. See "Public deployment" below.

**Production vs. dev vs. public-demo code**: three tiers, not two.
- `core/api/main.py` (full backend) + `tools/` (chunk-viewer, dev-dashboard) — your own local admin tooling: ingest, seed the golden set, inspect chunks. Never deployed publicly. Treat as production-grade code, but it only ever runs against `127.0.0.1`.
- `core/api/public_main.py` (lite backend) + `apps/demo` (frontend) — the actual shipped, internet-facing surface. The lite backend deliberately mounts only search + read-only document/PDF routes scoped to `golden_user`; upload/eval/mutation routes are never imported into it, so there's nothing to lock down. This is real production code serving real traffic.

## Commands

```bash
# Setup (Windows)
.venv\Scripts\activate
pip install -r requirements.txt

# Extract+chunk debug demo (prints first 5 chunks; not part of the real ingest path — that's POST /upload/bulk)
python -m core.main
python -m core.main <pdf_path>

# Dev server (full backend — local admin use only, never deployed)
uvicorn core.api.main:app --reload

# Lite public backend (what's actually deployed to Render)
uvicorn core.api.public_main:app --reload --port 8001

# Dev dashboard: upload PDFs, run searches, manage documents/dates against the live API
cd tools/dev-dashboard && npm install && npm run dev   # http://localhost:5173

# Chunk viewer: inspect raw extraction/chunking output for a PDF, no embedding/search involved
cd tools/chunk-viewer && npm install && npm run dev    # http://localhost:5173 (run one tool at a time)

# Public demo frontend (landing + /demo/) — what's deployed to Vercel
cd apps/demo && npm install && npm run dev             # http://localhost:5174

# Tests
pytest
pytest -v
pytest tests/query/test_parser.py            # single file
pytest tests/chunking/test_chunker.py::test_name  # single test

# Eval framework
python -m core.eval <golden_set.json>

# Seed/reseed the golden_user demo corpus (admin-only; run against the full backend, never public_main)
curl -X POST http://127.0.0.1:8000/eval/seed
```

`pytest.ini` sets `pythonpath = .`, so tests import via `core.xxx` without install.

Config is via `.env` (copy from `.env.example`): `QUERYNEST_DATABASE_URL` (Supabase/Postgres connection string — use the **pooler** connection string `aws-0-<region>.pooler.supabase.com:6543`, not the direct `db.<ref>.supabase.co` host, which is IPv6-only and unreachable from Docker/Render) and `QUERYNEST_STORAGE_MODE` (`supabase` or `local`). With no `QUERYNEST_DATABASE_URL` set, the API falls back to an in-memory store. Supabase Storage (PDF files, separate from the Postgres connection) needs `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET`. The public backend also needs `QUERYNEST_DEMO_ORIGIN` (comma-separated allowed CORS origins).

## Public deployment

- **Backend** (`core/api/public_main.py`) → Render, Dockerfile at repo root, config in `render.yaml`. Only mounts `health`, `public_search`, `public_documents` routers — structurally cannot upload, reseed, or mutate anything, so it needs no auth layer.
- **Frontend** (`apps/demo`) → Vercel, root directory `apps/demo`. Two static pages via native Vite multi-page build: `index.html` (landing) and `demo/index.html` (the `/demo/` route) — no router dependency. `VITE_API_BASE` points at the Render URL.
- **Storage**: DB and PDFs both live in the same Supabase project the full backend uses locally — `core/storage/` (mirrors `core/index/`'s `VectorStore` pattern) picks `LocalFileStore` or `SupabaseFileStore` off `QUERYNEST_STORAGE_MODE`. Seeding/reseeding the golden set happens by running the full backend **locally** against that Supabase project and hitting `/eval/seed` — the public backend never seeds itself.
- **Keep-alive**: `.github/workflows/keepalive.yml` pings `/health` every 10 min so Render's free tier doesn't spin down (best-effort — GitHub's cron scheduler isn't exact; upgrade to a paid Render plan for a hard guarantee).
- **Health check naming**: the frontend polls `/check-backend`, not `/health` — ad-blockers (Brave Shields included) commonly filter generic paths like `/health`/`/ping`/`/beacon` as tracking pings, silently failing the request client-side. `/health` still exists (used by the keep-alive ping, which runs server-side and is unaffected) but the browser-facing connectivity check must use `/check-backend`.

## Architecture

### Pipeline

```
PDF → pymupdf4llm → ExtractedDocument → chunker → List[Chunk] → fastembed → VectorStore
```

1. **Extract** (`core/ingest/extractor.py`): pymupdf4llm produces `ExtractedDocument` with `ExtractedBlock`s (text, page, bbox, type). `core/ingest/date_extractor.py` resolves a document date via a fallback chain: user input → filename → PDF metadata → content → null.
2. **Chunk** (`core/chunking/chunker.py`): Groups blocks by `section-header` type, flushes on heading boundary or token overflow (MAX_TOKENS=400, MIN_TOKENS=120).
3. **Embed** (`core/embedding/`): fastembed with `BAAI/bge-small-en-v1.5` (384-dim, ONNX, CPU). `base.py` defines the interface, `fastembed.py` the implementation.
4. **Index** (`core/index/`): `VectorStore` ABC (`base.py`) defines `store_chunks`, `search`, `list_documents`, `update_document_date`, `delete_document`, `close`. Two implementations: `pgvector.py` (Supabase Postgres) and `local.py` (local Postgres). `config.py`'s `get_vector_store()` picks the implementation based on `QUERYNEST_STORAGE_MODE`.
5. **Store PDF files** (`core/storage/`): `FileStore` ABC (`base.py`) defines `save`, `get`, `delete`, `delete_all` — mirrors the `VectorStore` split exactly. `local.py` writes to `data/uploads/`; `supabase.py` calls the Supabase Storage REST API directly via `requests` (no SDK dependency). `config.py`'s `get_file_store()` picks the implementation off the same `QUERYNEST_STORAGE_MODE` env var `core/index/config.py` uses.
6. **Query parsing** (`core/query/parser.py`): Regex-based extraction of natural-language date expressions from search queries (e.g. "last 3 years", "in 2020", "from 2020 to 2023"), returning a `ParsedQuery` with the cleaned query text plus `date_from`/`date_to`. Search combines this semantic query with a date pre-filter in the same store query.

No circular dependencies between these stages — keep it that way.

### Data Models

- `ExtractedBlock` / `ExtractedPage` / `ExtractedDocument` (`core/models/extracted.py`): one PDF span, one page, one document.
- `Chunk` (`core/models/chunk.py`): joined paragraph text, source blocks, heading, chunk_index.
- `SearchResult` / `SourceBlock` / `DocumentInfo` (`core/index/base.py`): search/index-layer types, separate from the ingestion-layer models above.

### API (`core/api/`)

**Full backend** (`main.py`, local admin use only — never deployed):
- FastAPI app; lifespan hook calls `store.setup()` when `QUERYNEST_DATABASE_URL` is set, otherwise runs in-memory-only.
- `routes/`: `upload` (bulk upload, background job status), `documents` (list/chunks/date override), `search`, `eval`, `health`.
- `jobs.py`: thread-safe in-process job tracker for background bulk-upload progress (not persisted, not for production scale).
- `store.py`: in-memory chunk store used by the chunk-viewer dev tool (separate from the vector store).
- `constants.py`: `GOLDEN_USER = "golden_user"`, shared by `eval.py` and the public routes below.

**Lite public backend** (`public_main.py` — deployed to Render, the real production surface):
- Its own `FastAPI()` instance, not a flag on `main.py`. Mounts only `health`, `public_search`, `public_documents` — nothing else is imported, so upload/eval/mutation are structurally unreachable, not just unauthenticated.
- `routes/public_search.py`: `POST /search` — no `user_id` field accepted from the client at all; always searches `GOLDEN_USER`. Includes a small in-memory IP rate limiter (this route is fully public with zero auth).
- `routes/public_documents.py`: `GET /documents` (read-only golden-corpus listing), `GET /documents/{id}/pdf` (read-only, `GOLDEN_USER`-scoped; `?download=true` sets `Content-Disposition: attachment`).
- CORS restricted to `QUERYNEST_DEMO_ORIGIN` (no `localhost`, no wildcard).

### Eval framework (`core/eval/`)

Golden-query-set based retrieval evaluation: `runner.py` executes queries against the API/store, `metrics.py` computes precision/recall/nDCG/MRR, `report.py` formats output, `download_pdfs.py` fetches fixture PDFs. Exposed via `core/api/routes/eval.py` and `python -m core.eval`.

## Design Decisions

See `docs/decisions.md` for full rationale.

- **D1**: Document-aware chunking (heading-based, not semantic)
- **D2**: pgvector in Supabase Postgres for storage
- **D3**: Desktop offline/cloud, mobile/web cloud-only
- **D4**: Embedding model — fastembed with BAAI/bge-small-en-v1.5 (384 dims, ONNX, 67MB)
- **D5**: Date extraction chain — user input → filename → PDF metadata → content → null
- **D6**: NL query parsing — regex-based date extraction from search queries
- **D15**: Public demo backend is a separate app (`public_main.py`), not an auth flag on the full one
- **D16**: PDF storage abstraction (`core/storage/`) — same local/hosted split as `VectorStore`

## Error Handling

- `ValueError` for invalid input (wrong file type, empty queries)
- `RuntimeError` for infrastructure failures (PDF load failure, model download)

## Rules

✅ Always:
- Run tests before committing
- Follow existing code conventions
- Keep modules independent (no circular dependencies)
- Ask when architectural direction is ambiguous

⚠️ Ask before:
- Modifying data models (`ExtractedBlock`, `Chunk`, `SearchResult`, `DocumentInfo`)
- Adding new dependencies
- Changing embedding model or dimensions
- Refactoring more than 3 files at once

🚫 Never:
- Commit secrets, API keys, or credentials
- Modify CI config without explicit instruction
- Delete test fixtures or snapshot files
- Touch `.env` (read or write) — ask the user first if a change or value from it is needed
- Read, write, or run commands outside this project folder — ask the user first if something outside is needed
- Run `git commit` — the user's local git setup requires a password Claude can't enter. Instead, stage the relevant changes (or tell the user what to stage) and propose a commit message following Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, etc.), then ask the user to run the commit themselves.
