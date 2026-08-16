# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

QueryNest is a local-first, AI-powered semantic search engine for personal PDFs. Only `core/` (the shared Python engine) is implemented; `apps/` (web/mobile/desktop frontends) and `packages/` are placeholders for future work.

The project is mid-pivot (see Planned Direction below). `docs/ARCHITECTURE.md` describes the pre-pivot design and is stale in places (FAISS, SQLite); trust the code and this file over it.

## Commands

```bash
# Setup (Windows; .venv already exists in this repo)
.venv\Scripts\activate
pip install -r requirements.txt

# Run the full pipeline demo (ingest sample PDF + search)
python -m core.main

# Ingest a specific PDF
python -m core.main ingest <pdf_path>

# Search the index
python -m core.main search <query>

# Tests
pytest
pytest -v
pytest tests/ingest/test_extractor.py          # single file
pytest tests/ingest/test_extractor.py::test_name  # single test
```

`pytest.ini` sets `pythonpath = .`, so tests import via `core.xxx` without install. There is no lint/format config in the repo currently.

## Architecture

The core engine is a linear pipeline, each stage a standalone module with no circular dependencies:

```
Ingest -> Normalize -> Cleanup -> Chunk -> Embed -> Index -> Search -> Highlight
```

`core/main.py` wires the whole pipeline together and is the best reference for how modules compose (`ingest_pdf()` and `search_query()`). It's a CLI demo/manual-testing harness, not a designed entrypoint — expect it to be superseded by a proper API/CLI later.

### Stage-by-stage

- **`core/ingest/`**: `loader.py` opens PDFs via PyMuPDF. `extractor.py` walks page→block→line→span, producing one `TextBlock` per span (skips non-text blocks and empty spans). `normalizer.py` does two-pass reconstruction: `merge_spans_to_lines` (spans within `LINE_Y_TOLERANCE = 2.5pt`) then `merge_lines_to_paragraphs` (gap < `PARA_GAP = 10.0pt`; page breaks always start a new paragraph). `cleanup.py` strips repeated headers/footers (text on ≥3 pages in top/bottom 10% of page), page numbers, and junk/non-language paragraphs.

- **`core/chunking/`**: `chunker.py` greedily merges paragraphs into chunks, flushing on a heading boundary (once current chunk ≥ `MIN_TOKENS=120`) or token overflow (`MAX_TOKENS=400`). `heading.py` heuristically detects headings (numbered `1.2.3 Title`, roman numerals, ALL-CAPS short lines, ≤40 chars). `tokenizer.py` estimates tokens as `word_count * 1.3` — a rough heuristic, not a real tokenizer.

- **`core/embedding/`**: `base.py` defines `BaseEmbedder` (abstract) — implementations must return L2-normalized `float32` vectors so dot-product == cosine similarity. `local.py` implements `LocalEmbedder` using `fastembed` (ONNX runtime) with `BAAI/bge-small-en-v1.5` (384-dim) by default; queries get a `"query: "` prefix via `embed_query()`, passages do not. `factory.py`'s `get_embedder()` is the entry point; `use_cloud=True` raises `NotImplementedError` (cloud embedding not yet built).

- **`core/index/faiss_index.py`**: `FaissIndex` wraps `faiss.IndexFlatIP` (exact inner-product search, equals cosine similarity for normalized vectors). Maintains a parallel `List[IndexEntry]` mapping vector position → `(document_id, chunk_index)`. `remove_document()` rebuilds the index from scratch since `IndexFlat` has no native deletion. Persists as two files: `index.faiss` (binary) + `index_meta.json` (entry mapping); load via `FaissIndex.load(directory)`. **This module is being replaced — see Planned Direction.**

- **`core/search/`**, **`core/storage/`**: empty stubs, not yet implemented.

- **`core/models/`**: `TextBlock` (one PDF span: text, page, bbox, page_height) and `Chunk` (joined paragraph text, list of pages, list of per-paragraph bboxes — kept separate rather than merged so each paragraph can be highlighted independently).

- **`core/config.py`**: currently empty; planned config lives in `docs/ARCHITECTURE.md` as a `QueryNestConfig` dataclass — not yet implemented.

Chunk data is currently persisted ad hoc as JSON sidecars (`<document_id>_chunks.json`) next to the FAISS index in `.querynest_data/`, written directly from `core/main.py` — there is no `core/storage/` implementation yet.

### Design notes worth knowing before changing these modules

- `TextBlock.page_height` is stored per-block (not looked up later) since it's cheap to grab during extraction and needed for header/footer position checks.
- `Chunk` keeps one bbox per source paragraph rather than a merged bbox, specifically to support precise per-paragraph PDF highlighting later.
- Error handling convention: `ValueError` for invalid input (wrong file type, empty queries), `RuntimeError` for infrastructure failures (PDF load failure, model download failure).

## Planned Direction

These changes have been decided but are **not yet implemented** — treat them as the target architecture, not the current state:

1. **Storage: pgvector instead of FAISS + Postgres.** Vectors live as a `pgvector` column in Postgres alongside document/chunk metadata. Drops the separate FAISS index file. Postgres is a server process — "local" means a locally-run Postgres instance, a real tradeoff for the local-first goal.
2. **Hybrid search: metadata + semantic.** Structured metadata filtering (subject, year range, doc type) combined with pgvector similarity search — not semantic search alone.
3. **Ingestion: PyMuPDF4LLM instead of raw PyMuPDF.** Markdown/structure-aware extraction, reducing custom heuristics in `normalizer.py`/`heading.py`.
4. **Answer generation with citations.** Retrieval produces both highlighted source passages and a generated answer with citations back to specific chunks/pages.

### Future scope (not scheduled)

- **Multimodal ingestion**: scanned documents, handwritten notes, image-based PDFs (OCR / vision-model extraction).

## Testing

- Uses `pytest` with a real PDF fixture, `tests/fixtures/sample.pdf` ("Attention Is All You Need"), not mocked data.
- Test layout mirrors `core/` (`tests/ingest/`, `tests/embedding/`, `tests/index/`).

## Rules

✅ Always:
- Run tests before committing changes
- Follow existing code conventions in the module you're editing
- Use `ValueError` for invalid input, `RuntimeError` for infrastructure failures
- Keep modules independent (no circular dependencies)
- Ask questions when architectural direction is ambiguous

⚠️ Ask before:
- Modifying the data models (`TextBlock`, `Chunk`) — these have downstream consumers
- Adding new dependencies
- Changing the embedding model or dimensions
- Refactoring more than 3 files at once

🚫 Never:
- Commit secrets, API keys, or credentials
- Modify CI/pipeline config without explicit instruction
- Change `pytest.ini` settings without asking
- Delete test fixtures or snapshot files
- Assume FAISS/SQLite is the long-term storage — pgvector is the target
