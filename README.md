# QueryNest

An AI-powered semantic search engine for personal PDFs. Search by meaning, not keywords — find information across all your documents and jump straight to the highlighted passage.

**Live demo**: [querynest.apoorvm.com/demo/](https://querynest.apoorvm.com/demo/) — read-only, searches a fixed 18-document corpus, no sign-up. [querynest.apoorvm.com](https://querynest.apoorvm.com) has the landing page.

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
| PDF storage abstraction (local disk / Supabase Storage) | Done |
| Public demo (lite backend + landing/demo frontend, deployed) | Done |
| Dev tools (chunk-viewer, dev-dashboard) | Done |
| Tests (139 passing) | Done |

### Planned

| Module | Status |
|---|---|
| Answer generation with citations | Planned |
| PDF highlight annotation | Planned |

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
# Supabase connection string — use the pooler string, not the direct db.<ref>.supabase.co
# host. The direct host is IPv6-only; Docker and most PaaS hosts (Render included) have no
# IPv6 route, so it fails with "Network is unreachable" outside a plain local Python process.
QUERYNEST_DATABASE_URL=postgresql://postgres.[ref]:[pass]@aws-0-[region].pooler.supabase.com:6543/postgres

# Storage mode: "supabase" or "local"
QUERYNEST_STORAGE_MODE=supabase

# Supabase Storage (PDF files) — separate from the Postgres connection above.
# Only needed when QUERYNEST_STORAGE_MODE=supabase.
SUPABASE_URL=https://[ref].supabase.co
SUPABASE_SERVICE_ROLE_KEY=[service role key, never the anon key]
SUPABASE_STORAGE_BUCKET=pdfs
```

### Running the Backend

```bash
# Run the full backend (local admin use: ingest, seed, inspect — never deployed)
uvicorn core.api.main:app --reload

# Run the lite public backend (what's actually deployed to Render)
uvicorn core.api.public_main:app --reload --port 8001

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

### Public Demo Frontend

The landing page + live demo, deployed to Vercel. Locally:

```bash
cd apps/demo
npm install
npm run dev
```

Opens at `http://localhost:5174` — `/` is the landing page, `/demo/` is the live search demo. Proxies `/api` to the lite public backend on `:8001` in dev (see `apps/demo/vite.config.ts`).

---

## API Endpoints

### Full backend (`core.api.main` — local admin use, never deployed)

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | App info |
| `GET` | `/health` | Health check |
| `GET` | `/check-backend` | Same as `/health`, under a name ad-blockers don't filter |
| `POST` | `/upload/bulk` | Upload PDFs (background processing) |
| `GET` | `/upload/{job_id}/status` | Poll upload progress |
| `GET` | `/documents` | List all documents for a user |
| `GET` | `/documents/{id}/chunks` | Get chunks for a document |
| `PATCH` | `/documents/{id}/date` | Override detected date |
| `GET` | `/documents/{id}/pdf` | Fetch a document's PDF (`?download=true` to force download) |
| `POST` | `/search` | Search with NL query + date filtering |
| `POST` | `/eval/seed` | Re-seed the golden demo corpus for `golden_user` |

### Lite public backend (`core.api.public_main` — deployed to Render)

Everything here is scoped to `golden_user` server-side; no `user_id` is ever accepted from the client, and upload/eval/mutation routes simply aren't mounted.

| Method | Path | Description |
|---|---|---|
| `GET` | `/health`, `/check-backend` | Health check |
| `GET` | `/documents` | List the golden demo corpus |
| `GET` | `/documents/{id}/pdf` | Fetch a demo PDF (`?download=true` to force download) |
| `POST` | `/search` | Search the golden demo corpus (rate-limited) |

---

## Testing

```bash
pytest              # Run all tests (139)
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
│   ├── storage/                 # PDF file storage (Supabase Storage / local disk)
│   ├── query/                   # NL query parsing (date extraction)
│   ├── models/                  # Data models
│   ├── eval/                    # Golden-set retrieval evaluation
│   ├── api/                     # FastAPI backends
│   │   ├── routes/              # Endpoint modules (upload, search, public_search, etc.)
│   │   ├── main.py              # Full backend — local admin use, never deployed
│   │   ├── public_main.py       # Lite backend — deployed to Render
│   │   ├── jobs.py              # Background job tracking
│   │   └── store.py             # In-memory store (chunk viewer)
│   └── main.py                  # CLI entry point
├── apps/
│   └── demo/                    # Public landing + demo frontend, deployed to Vercel
├── tools/
│   ├── chunk-viewer/            # Inspect extraction + chunking output
│   └── dev-dashboard/           # Upload, search, manage documents
├── tests/                       # Test suite (139 tests)
├── docs/                        # Architecture decisions, evaluation
├── .github/workflows/           # Keep-alive ping for the Render backend
├── .env.example                 # Configuration template
├── Dockerfile                   # Public backend image (core.api.public_main)
├── render.yaml                  # Render deploy config
├── requirements.txt
└── pyproject.toml
```

---

## Deployment

The public demo runs on three services, all wired to the same Supabase project:

- **Frontend** — Vercel, `apps/demo` as the project root, custom domain `querynest.apoorvm.com`.
- **Backend** — Render, Dockerfile-based web service (`render.yaml`), running `core.api.public_main`. Kept warm by `.github/workflows/keepalive.yml` (pings `/health` every 10 min — Render's free tier spins down after ~15 min idle).
- **Data** — Supabase Postgres (pgvector) + Supabase Storage (PDF files). The golden demo corpus is seeded/reseeded by running the full backend **locally** and calling `POST /eval/seed` — the deployed public backend never writes anything.

Full rationale in `docs/decisions.md` (D15, D16) and `docs/ARCHITECTURE.md`'s "Current Deployment" section — including the Supabase pooler-vs-direct-connection gotcha (the direct host is IPv6-only and unreachable from Docker/Render).

---

## Architecture Decisions

See [docs/decisions.md](docs/decisions.md) for full rationale.

- **D1**: Document-aware chunking (heading-based, not semantic)
- **D2**: pgvector in Supabase Postgres for storage
- **D3**: Platform split (desktop offline/cloud, mobile/web cloud-only)
- **D4**: Embedding model — fastembed with BAAI/bge-small-en-v1.5 (384 dims, ONNX, 67MB)
- **D5**: Date extraction chain — user input → filename → PDF metadata → content → null
- **D6**: NL query parsing — regex-based date extraction from search queries
- **D15**: Public demo backend is a separate app, not an auth flag on the full one
- **D16**: PDF storage abstraction — same local/hosted split as the vector store

---

## License

This project is under active development. License TBD.
