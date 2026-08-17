# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

QueryNest is an AI-powered semantic search engine for personal PDFs. Users search by meaning, get AI answers with citations, and see highlighted passages in the PDF.

**Current state**: Extraction + chunking pipeline implemented. Embedding, indexing, search, and answer generation are planned. The dev tools (FastAPI backend + chunk viewer) are for testing, not production.

## Commands

```bash
# Setup (Windows)
.venv\Scripts\activate
pip install -r requirements.txt

# Run pipeline
python -m core.main

# Dev server
uvicorn core.api.main:app --reload

# Tests
pytest
pytest -v
pytest tests/chunking/test_chunker.py::test_name  # single test
```

`pytest.ini` sets `pythonpath = .`, so tests import via `core.xxx` without install.

## Architecture

### Current Pipeline

```
PDF → pymupdf4llm → ExtractedDocument → chunker → List[Chunk]
```

Two stages, no circular dependencies:

1. **Extract** (`core/ingest/extractor.py`): pymupdf4llm produces `ExtractedDocument` with `ExtractedBlock`s (text, page, bbox, type)
2. **Chunk** (`core/chunking/chunker.py`): Groups blocks by `section-header` type, flushes on heading boundary or token overflow (MAX_TOKENS=400, MIN_TOKENS=120)

### Data Models

- `ExtractedBlock`: One PDF span (text, page, bbox, type like "text", "section-header", "table")
- `ExtractedPage`: Page number + list of blocks
- `ExtractedDocument`: Filename + list of pages
- `Chunk`: Joined paragraph text, source blocks, heading, chunk_index

### Dev Tools (Not Production)

- `core/api/`: FastAPI backend with `POST /upload` and `GET /documents/{doc_id}/chunks`
- `tools/chunk-viewer/`: React app for inspecting extraction/chunking output

## Design Decisions

See `docs/decisions.md` for rationale.

- **D1**: Document-aware chunking (heading-based, not semantic)
- **D2**: pgvector in Supabase Postgres for storage
- **D3**: Desktop offline/cloud, mobile/web cloud-only

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
- Modifying data models (`ExtractedBlock`, `Chunk`)
- Adding new dependencies
- Changing embedding model or dimensions
- Refactoring more than 3 files at once

🚫 Never:
- Commit secrets, API keys, or credentials
- Modify CI config without explicit instruction
- Delete test fixtures or snapshot files
