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
- **Minimum**: MIN_TOKENS = 120 (prevents tiny chunks)
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

- `base.py`: `VectorStore` ABC defining the storage contract — `setup()`, `store_chunks(...)`, `search(query_embedding, user_id, top_k, date_from, date_to) -> list[SearchResult]`, `list_documents(user_id) -> list[DocumentInfo]`, `update_document_date(document_id, user_id, document_date)`, `delete_document(document_id, user_id)`, `delete_all_for_user(user_id) -> int`, `close()`.
- `pgvector.py`: `PgVectorStore` — Supabase/hosted Postgres implementation.
- `local.py`: `LocalPgVectorStore` — local Postgres implementation, same schema/interface.
- `config.py`: `get_vector_store()` returns a cached singleton, picking `LocalPgVectorStore` or `PgVectorStore` based on `QUERYNEST_STORAGE_MODE` (`local` vs. default `supabase`).

**Input**: chunk texts, embeddings, and metadata (headings, pages, chunk indices, document date, source blocks)
**Output**: stored rows; `search()` returns ranked `SearchResult`s, optionally pre-filtered by a `[date_from, date_to]` range on `document_date`.

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
| `text` | `str` | Chunk text |
| `heading` | `str` | Section heading |
| `score` | `float` | Similarity score |
| `page` | `int` | Page of the chunk's first block |
| `document_date` | `date \| None` | Resolved document date |
| `source_blocks` | `list[SourceBlock]` | Blocks making up the chunk |

**DocumentInfo** — one row in a document listing.

| Field | Type | Description |
|---|---|---|
| `document_id` | `str` | Document id |
| `filename` | `str` | Original filename |
| `user_id` | `str` | Owning user |
| `document_date` | `date \| None` | Resolved document date |
| `chunk_count` | `int` | Number of chunks stored for the document |

---

## Module Details

### core/ingest/

- `extractor.py`: Single function `extract(pdf_path) -> ExtractedDocument`. Wraps pymupdf4llm JSON output.
- `date_extractor.py`: `extract_date(filename, pdf_metadata, first_page_text) -> tuple[date | None, str | None]`. Resolves a document date via the D5 fallback chain (filename → PDF metadata → content), returning the date plus which source it came from (`"filename"`, `"metadata"`, `"content"`, or `None`). Also exposes the individual `extract_date_from_filename`, `extract_date_from_metadata`, `extract_date_from_text` helpers.

### core/chunking/

- `chunker.py`: `chunk_document(doc) -> List[Chunk]`. Groups blocks by heading, flushes on boundary or overflow.
- `tokenizer.py`: `estimate_tokens(text) -> int`. Rough word-count-based estimate.

### core/embedding/

- `base.py`: `BaseEmbedder` ABC.
- `fastembed.py`: `FastEmbedEmbedder`, cached singleton via `get_instance()`.

### core/index/

- `base.py`: `VectorStore` ABC, `SourceBlock`, `SearchResult`, `DocumentInfo`.
- `pgvector.py`: `PgVectorStore` (Supabase/hosted Postgres).
- `local.py`: `LocalPgVectorStore` (local Postgres, same schema).
- `config.py`: `get_vector_store()` — picks an implementation from `QUERYNEST_STORAGE_MODE` and caches it.

### core/query/

- `parser.py`: `parse_query(query) -> ParsedQuery`. Regex-based NL date-range extraction (see Stage 5 above).

### core/models/

- `extracted.py`: `ExtractedBlock`, `ExtractedPage`, `ExtractedDocument`
- `chunk.py`: `Chunk`

### core/eval/

Golden-query-set retrieval evaluation. See `docs/evaluation.md` for full methodology.

- `runner.py`: `load_golden(path) -> list[EvalQuery]` parses the golden dataset; `run_search(query_text, top_k)` calls `POST /api/search` on a running API instance; `run_eval(golden_path, top_k) -> list[QueryResult]` runs every golden query and computes precision@{5,10}, recall@{5,10}, nDCG@10, and MRR per query.
- `metrics.py`: `precision_at_k`, `recall_at_k`, `ndcg_at_k`, `mrr` — pure functions over retrieved/relevant id lists.
- `report.py`: `print_report(results)` prints a console summary; `generate_report(results, output_dir)` writes a timestamped, git-commit-tagged JSON report (aggregate metrics, by-type breakdown, worst queries by MRR, per-query results) to `reports/`.
- `download_pdfs.py`: Fetches the fixture PDFs used by the golden dataset into `data/eval/pdfs/<category>/`.
- `__main__.py`: `python -m core.eval` — runs `run_eval` against `data/eval/golden.json`, prints the report, and saves it to `reports/`.

### core/api/ (Dev Only)

- `main.py`: FastAPI app; CORS for `localhost:5173`; lifespan hook calls `store.setup()` when `QUERYNEST_DATABASE_URL` is set, otherwise runs in-memory-only.
- `routes/`: route modules, assembled in `routes/__init__.py` as `api_router`.
  - `health.py`: `GET /`, `GET /health`
  - `upload.py`: `POST /upload/bulk` (background bulk upload — extracts, chunks, date-detects, and, when a database is configured, embeds and stores each file), `GET /upload/{job_id}/status` (per-file job progress)
  - `documents.py`: `GET /documents`, `GET /documents/{doc_id}/chunks`, `PATCH /documents/{doc_id}/date`, `GET /documents/{doc_id}/pdf`
  - `search.py`: `POST /search` — parses NL date expressions out of the query, embeds the remaining text, and runs a hybrid (semantic + date-filtered) store search
  - `eval.py`: `POST /eval/seed` (background job that re-indexes the eval fixture PDFs for a dedicated `golden_user`), `GET /eval/seed/{job_id}/status`
- `jobs.py`: Thread-safe in-process `Job`/`FileStatus` tracker for background bulk-upload and eval-seed progress (not persisted, not for production scale).
- `store.py`: In-memory chunk store used by the chunk-viewer dev tool (separate from the vector store).

### tools/chunk-viewer/ (Dev Only)

React + TypeScript + Vite app for inspecting extraction output. Shows chunk list, source blocks, and metadata.

---

## Production Architecture

### Platform Strategy

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
- HNSW index for approximate nearest neighbor search
- SQL WHERE clauses for metadata filtering (year, subject, type)
- Row-level security for user isolation

**Local Mode** (Desktop only):
- PostgreSQL with pgvector extension running locally
- Same schema as Supabase for consistency
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
