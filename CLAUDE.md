# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

QueryNest is a local-first, AI-powered semantic search engine for personal PDFs. Only `core/` (the shared Python engine) is implemented; `apps/` (web/mobile/desktop frontends) and `packages/` are placeholders for future work.

The project is mid-pivot on several fronts (see [Planned Direction](#planned-direction) below) — when reading the code, don't assume the current implementation matches the target architecture. `docs/ARCHITECTURE.md` describes the pre-pivot design and is stale in places (FAISS, SQLite); trust the code and this file over it until it's rewritten.

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

## Architecture (current implementation)

The core engine is a linear pipeline, each stage a standalone module with no circular dependencies:

```
Ingest -> Normalize -> Cleanup -> Chunk -> Embed -> Index -> Search -> Highlight
```

`core/main.py` wires the whole pipeline together and is the best reference for how modules compose (`ingest_pdf()` and `search_query()`). It's a CLI demo/manual-testing harness, not a designed entrypoint — expect it to be superseded by a proper API/CLI later.

### Stage-by-stage

- **`core/ingest/`**: `loader.py` opens PDFs via PyMuPDF. `extractor.py` walks page→block→line→span, producing one `TextBlock` per span (skips non-text blocks and empty spans). `normalizer.py` does two-pass reconstruction: `merge_spans_to_lines` (spans within `LINE_Y_TOLERANCE = 2.5pt`) then `merge_lines_to_paragraphs` (gap < `PARA_GAP = 10.0pt`; page breaks always start a new paragraph). `cleanup.py` strips repeated headers/footers (text on ≥3 pages in top/bottom 10% of page), page numbers, and junk/non-language paragraphs.

- **`core/chunking/`**: `chunker.py` greedily merges paragraphs into chunks, flushing on a heading boundary (once current chunk ≥ `MIN_TOKENS=120`) or token overflow (`MAX_TOKENS=400`). `heading.py` heuristically detects headings (numbered `1.2.3 Title`, roman numerals, ALL-CAPS short lines, ≤40 chars). `tokenizer.py` estimates tokens as `word_count * 1.3` — a rough heuristic, not a real tokenizer.

- **`core/embedding/`**: `base.py` defines `BaseEmbedder` (abstract) — implementations must return L2-normalized `float32` vectors so dot-product == cosine similarity. `local.py` implements `LocalEmbedder` using `fastembed` (ONNX runtime) with `BAAI/bge-small-en-v1.5` (384-dim) by default; queries get a `"query: "` prefix via `embed_query()`, passages do not. `factory.py`'s `get_embedder()` is the entry point; `use_cloud=True` raises `NotImplementedError` (cloud embedding not yet built).

- **`core/index/faiss_index.py`**: `FaissIndex` wraps `faiss.IndexFlatIP` (exact inner-product search, equals cosine similarity for normalized vectors). Maintains a parallel `List[IndexEntry]` mapping vector position → `(document_id, chunk_index)`. `remove_document()` rebuilds the index from scratch since `IndexFlat` has no native deletion. Persists as two files: `index.faiss` (binary) + `index_meta.json` (entry mapping); load via `FaissIndex.load(directory)`. **This module is being replaced — see [Planned Direction](#planned-direction).**

- **`core/search/`**, **`core/storage/`**: empty stubs, not yet implemented.

- **`core/models/`**: `TextBlock` (one PDF span: text, page, bbox, page_height) and `Chunk` (joined paragraph text, list of pages, list of per-paragraph bboxes — kept separate rather than merged so each paragraph can be highlighted independently).

- **`core/config.py`**: currently empty; planned config lives in `docs/ARCHITECTURE.md` as a `QueryNestConfig` dataclass (embedding model/dim, chunk token bounds, top_k, storage paths, highlight color) — not yet implemented.

Chunk data is currently persisted ad hoc as JSON sidecars (`<document_id>_chunks.json`) next to the FAISS index in `.querynest_data/`, written directly from `core/main.py` — there is no `core/storage/` implementation yet.

### Design notes worth knowing before changing these modules

- `TextBlock.page_height` is stored per-block (not looked up later) since it's cheap to grab during extraction and needed for header/footer position checks.
- `Chunk` keeps one bbox per source paragraph rather than a merged bbox, specifically to support precise per-paragraph PDF highlighting later.
- Error handling convention: `ValueError` for invalid input (wrong file type, empty queries), `RuntimeError` for infrastructure failures (PDF load failure, model download failure).

See `docs/ARCHITECTURE.md` for the fuller design doc, but read it critically — parts of it describe the pre-pivot (FAISS/SQLite) design.

## Planned Direction

The following changes to the plan have been decided but are **not yet implemented in code** — treat them as the target architecture to build toward, not the current state:

1. **Storage: pgvector instead of FAISS + Postgres.** Drop the separate FAISS index file entirely; vectors live as a `pgvector` column directly in Postgres alongside document/chunk metadata. This replaces `core/index/faiss_index.py` and unifies what would have been two storage systems (metadata DB + vector index) into one. Note: unlike SQLite/FAISS, Postgres is a server process, not an embeddable library — "local" here means a locally-run Postgres instance (native install, container, or bundled binary), which is a real packaging tradeoff for the local-first goal, not yet resolved. PDF files themselves stay on the local filesystem, referenced by path from a Postgres row — no object storage needed unless cloud sync is added later.
2. **Hybrid search: metadata + semantic.** Queries like *"QP of [subject], last 3 years"* need structured metadata filtering (subject, year range, doc type) combined with semantic vector search — not semantic search alone. `core/search/` should parse structured filters out of the query and combine them with the pgvector similarity search (e.g., filter-then-rank or a combined SQL query).
3. **Ingestion: PyMuPDF4LLM instead of raw PyMuPDF.** `core/ingest/loader.py` and `extractor.py` will move to `pymupdf4llm` for extraction, which is markdown/structure-aware and should reduce the amount of custom heading/paragraph-reconstruction heuristics needed in `normalizer.py`/`heading.py`.
4. **Answer generation with citations, alongside highlighting.** Retrieval should produce both: the highlighted source passage(s) in the original PDF, and a generated answer with citations back to the specific chunks/pages it drew from. Highlighting is largely already designed for (see `Chunk.bboxes`); the citation-generation layer is new.

### Future scope (not scheduled yet)

- **Multimodal ingestion**: scanned documents, handwritten notes, and image-based PDFs (OCR / vision-model extraction), extending beyond the current text-only PyMuPDF(4LLM) pipeline.

### Cross-cutting focus areas

- **Tests & evaluation**: beyond unit tests of pipeline mechanics, build an evaluation harness that measures retrieval/answer quality (e.g., precision/recall on a query set, citation accuracy) and tracks these metrics over time, so a given change's impact on quality can be measured, not just its effect on green/red tests.
- **Impact over features**: prioritize evidence that a change solves a real, observed problem (a real search failure, a real user need) over adding capability for its own sake. When proposing or reviewing work, prefer the option with a concrete before/after signal.

## Testing

- Uses `pytest` with a real PDF fixture, `tests/fixtures/sample.pdf` ("Attention Is All You Need"), not mocked data — most tests exercise the actual pipeline against it.
- Test layout mirrors `core/` (`tests/ingest/`, `tests/embedding/`, `tests/index/`).
- See "Cross-cutting focus areas" above — evaluation/metrics tracking is a planned addition to this, not yet built.
