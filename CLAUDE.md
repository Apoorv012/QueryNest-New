# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

QueryNest is an AI-powered semantic search engine for personal PDFs. Users search by meaning, get AI answers with citations, and see highlighted passages in the PDF.

**Current state**: Extraction, chunking, embedding, indexing (pgvector), hybrid search (semantic + NL date filtering), background bulk upload, and an eval framework are implemented. Answer generation with citations and PDF highlight annotation are planned.

**Production vs. dev tools**: The FastAPI backend (`core/api/`) is the real backend — treat it as production code. The chunk viewer and dev dashboard (`tools/`) are dev-only UIs for testing/inspection, not shipped.

## Commands

```bash
# Setup (Windows)
.venv\Scripts\activate
pip install -r requirements.txt

# Extract+chunk debug demo (prints first 5 chunks; not part of the real ingest path — that's POST /upload/bulk)
python -m core.main
python -m core.main <pdf_path>

# Dev server (production backend)
uvicorn core.api.main:app --reload

# Dev dashboard: upload PDFs, run searches, manage documents/dates against the live API
cd tools/dev-dashboard && npm install && npm run dev   # http://localhost:5173

# Chunk viewer: inspect raw extraction/chunking output for a PDF, no embedding/search involved
cd tools/chunk-viewer && npm install && npm run dev    # http://localhost:5173 (run one tool at a time)

# Tests
pytest
pytest -v
pytest tests/query/test_parser.py            # single file
pytest tests/chunking/test_chunker.py::test_name  # single test

# Eval framework
python -m core.eval <golden_set.json>
```

`pytest.ini` sets `pythonpath = .`, so tests import via `core.xxx` without install.

Config is via `.env` (copy from `.env.example`): `QUERYNEST_DATABASE_URL` (Supabase/Postgres connection string) and `QUERYNEST_STORAGE_MODE` (`supabase` or `local`). With no `QUERYNEST_DATABASE_URL` set, the API falls back to an in-memory store.

## Architecture

### Pipeline

```
PDF → pymupdf4llm → ExtractedDocument → chunker → List[Chunk] → fastembed → VectorStore
```

1. **Extract** (`core/ingest/extractor.py`): pymupdf4llm produces `ExtractedDocument` with `ExtractedBlock`s (text, page, bbox, type). `core/ingest/date_extractor.py` resolves a document date via a fallback chain: user input → filename → PDF metadata → content → null.
2. **Chunk** (`core/chunking/chunker.py`): Groups blocks by `section-header` type, flushes on heading boundary or token overflow (MAX_TOKENS=400, MIN_TOKENS=120).
3. **Embed** (`core/embedding/`): fastembed with `BAAI/bge-small-en-v1.5` (384-dim, ONNX, CPU). `base.py` defines the interface, `fastembed.py` the implementation.
4. **Index** (`core/index/`): `VectorStore` ABC (`base.py`) defines `store_chunks`, `search`, `list_documents`, `update_document_date`, `delete_document`, `close`. Two implementations: `pgvector.py` (Supabase Postgres) and `local.py` (local Postgres). `config.py`'s `get_vector_store()` picks the implementation based on `QUERYNEST_STORAGE_MODE`.
5. **Query parsing** (`core/query/parser.py`): Regex-based extraction of natural-language date expressions from search queries (e.g. "last 3 years", "in 2020", "from 2020 to 2023"), returning a `ParsedQuery` with the cleaned query text plus `date_from`/`date_to`. Search combines this semantic query with a date pre-filter in the same store query.

No circular dependencies between these stages — keep it that way.

### Data Models

- `ExtractedBlock` / `ExtractedPage` / `ExtractedDocument` (`core/models/extracted.py`): one PDF span, one page, one document.
- `Chunk` (`core/models/chunk.py`): joined paragraph text, source blocks, heading, chunk_index.
- `SearchResult` / `SourceBlock` / `DocumentInfo` (`core/index/base.py`): search/index-layer types, separate from the ingestion-layer models above.

### API (`core/api/`, dev tool)

- `main.py`: FastAPI app; lifespan hook calls `store.setup()` when `QUERYNEST_DATABASE_URL` is set, otherwise runs in-memory-only.
- `routes/`: `upload` (bulk upload, background job status), `documents` (list/chunks/date override), `search`, `eval`, `health`.
- `jobs.py`: thread-safe in-process job tracker for background bulk-upload progress (not persisted, not for production scale).
- `store.py`: in-memory chunk store used by the chunk-viewer dev tool (separate from the vector store).

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
