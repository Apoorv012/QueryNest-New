# QueryNest

An AI-powered semantic search engine for personal PDFs. Search by meaning, not keywords — find information across all your documents and jump straight to the highlighted passage.

---

## What It Does

- **Semantic Search**: Understands meaning — search "operating system concepts" and find every relevant paper, even if those exact words never appear
- **In-Document Highlighting**: Relevant passages are highlighted in yellow directly in the PDF
- **AI Answers with Citations**: Generated answers include citations back to specific chunks/pages
- **Hybrid Filtering**: Combine semantic search with metadata filters (date range, document type)
- **Natural Language Queries**: Type "papers from 2020 to 2023" — date parsing happens automatically

---

## Current Status

| Module | Status |
|---|---|
| PDF extraction (pymupdf4llm) | Done |
| Document-aware chunking | Done |
| Embedding pipeline (fastembed / BAAI/bge-small-en-v1.5) | Done |
| Vector index (pgvector in Supabase Postgres) | Done |
| Hybrid search (semantic + date pre-filter) | Done |
| Natural language date parsing | Done |
| Date extraction from PDFs | Done |
| Background bulk upload | Done |
| FastAPI backend | Done |
| Dev tools (chunk-viewer, dev-dashboard) | Done |
| Tests (65 passing) | Done |

### Planned

| Module | Status |
|---|---|
| Answer generation with citations | Planned |
| PDF highlight annotation | Planned |
| Evaluation framework | Planned |

---

## Getting Started

### Prerequisites

- Python 3.14+
- Node.js 18+ (for dev tools)
- PostgreSQL with pgvector extension (Supabase or local)

### Installation

```bash
git clone https://github.com/Apoorv012/QueryNest-New.git
cd QueryNest-New

python -m venv .venv
.venv\Scripts\activate    # Windows
source .venv/bin/activate # macOS/Linux

pip install -r requirements.txt
```

### Configuration

Copy `.env.example` to `.env` and fill in your database URL:

```bash
cp .env.example .env
```

```env
# Supabase connection string
QUERYNEST_DATABASE_URL=postgresql://postgres.[ref]:[pass]@aws-0-[region].pooler.supabase.com:6543/postgres

# Storage mode: "supabase" or "local"
QUERYNEST_STORAGE_MODE=supabase
```

### Running the Backend

```bash
# Run the dev server
uvicorn core.api.main:app --reload

# Run the CLI pipeline (ingest sample PDF)
python -m core.main

# Ingest a specific PDF
python -m core.main <pdf_path>
```

### Running the Dev Dashboard

The dev dashboard is a React app for uploading PDFs, searching, and inspecting results.

```bash
cd tools/dev-dashboard
npm install
npm run dev
```

Opens at `http://localhost:5173`.

**Features:**
- Upload PDFs (bulk, background processing with progress bar)
- Search with natural language queries (e.g. "transformer last 3 years")
- See all uploaded files with detected dates
- Override dates manually if needed

### Chunk Viewer

The chunk viewer is a separate tool for inspecting extraction and chunking output.

```bash
cd tools/chunk-viewer
npm install
npm run dev
```

Opens at `http://localhost:5173` (run one tool at a time, or change the port).

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | App info |
| `GET` | `/health` | Health check |
| `POST` | `/upload/bulk` | Upload PDFs (background processing) |
| `GET` | `/upload/{job_id}/status` | Poll upload progress |
| `GET` | `/documents` | List all documents for a user |
| `GET` | `/documents/{id}/chunks` | Get chunks for a document |
| `PATCH` | `/documents/{id}/date` | Override detected date |
| `POST` | `/search` | Search with NL query + date filtering |

---

## Testing

```bash
pytest              # Run all tests (65)
pytest -v           # Verbose output
pytest tests/query/test_parser.py  # Single file
```

---

## Project Structure

```
QueryNest-New/
├── core/                        # Python engine
│   ├── ingest/                  # PDF extraction + date extraction
│   ├── chunking/                # Document-aware chunking
│   ├── embedding/               # fastembed (BAAI/bge-small-en-v1.5)
│   ├── index/                   # pgvector storage (Supabase / local)
│   ├── query/                   # NL query parsing (date extraction)
│   ├── models/                  # Data models
│   ├── api/                     # FastAPI backend
│   │   ├── routes/              # Endpoint modules (upload, search, etc.)
│   │   ├── jobs.py              # Background job tracking
│   │   └── store.py             # In-memory store (chunk viewer)
│   └── main.py                  # CLI entry point
├── tools/
│   ├── chunk-viewer/            # Inspect extraction + chunking output
│   └── dev-dashboard/           # Upload, search, manage documents
├── tests/                       # Test suite (65 tests)
├── docs/                        # Architecture decisions, evaluation
├── .env.example                 # Configuration template
├── requirements.txt
└── pyproject.toml
```

---

## Architecture Decisions

See [docs/decisions.md](docs/decisions.md) for full rationale.

- **D1**: Document-aware chunking (heading-based, not semantic)
- **D2**: pgvector in Supabase Postgres for storage
- **D3**: Platform split (desktop offline/cloud, mobile/web cloud-only)
- **D4**: Embedding model — fastembed with BAAI/bge-small-en-v1.5 (384 dims, ONNX, 67MB)
- **D5**: Date extraction chain — user input → filename → PDF metadata → content → null
- **D6**: NL query parsing — regex-based date extraction from search queries

---

## License

This project is under active development. License TBD.
