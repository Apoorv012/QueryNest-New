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
PDF → pymupdf4llm → ExtractedDocument → chunker → List[Chunk]
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

---

## Module Details

### core/ingest/

- `extractor.py`: Single function `extract(pdf_path) -> ExtractedDocument`. Wraps pymupdf4llm JSON output.

### core/chunking/

- `chunker.py`: `chunk_document(doc) -> List[Chunk]`. Groups blocks by heading, flushes on boundary or overflow.
- `tokenizer.py`: `estimate_tokens(text) -> int`. Rough word-count-based estimate.

### core/models/

- `extracted.py`: `ExtractedBlock`, `ExtractedPage`, `ExtractedDocument`
- `chunk.py`: `Chunk`

### core/api/ (Dev Only)

- `main.py`: FastAPI app with CORS for localhost:5173
- `routes.py`: `POST /upload`, `GET /documents/{doc_id}/chunks`
- `store.py`: In-memory document/chunk storage

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
- **Embedding**: ~100ms per chunk on CPU (planned)
- **Search**: <50ms with HNSW index (planned)

GPU acceleration available for pymupdf4llm by switching `onnxruntime` to `onnxruntime-gpu` (drop-in replacement, no code changes).

---

## Future Scope

1. **Embedding pipeline**: fastembed with BAAI/bge-small-en-v1.5
2. **Vector index**: pgvector with HNSW
3. **Hybrid search**: Semantic + metadata filtering
4. **Answer generation**: LLM-based with citations
5. **PDF highlighting**: Syncfusion Flutter PDF Viewer annotations
6. **Offline ↔ online sync**: Desktop syncs with Supabase when online
7. **Cloud processing**: Mobile/web upload to cloud for processing (no desktop required)
