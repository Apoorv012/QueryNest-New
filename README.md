# QueryNest

An AI-powered semantic search engine for personal PDFs. Search by meaning, not keywords — find information across all your documents and jump straight to the highlighted passage.

---

## What It Does

- **Semantic Search**: Understands meaning — search "operating system concepts" and find every relevant paper, even if those exact words never appear
- **In-Document Highlighting**: Relevant passages are highlighted in yellow directly in the PDF
- **AI Answers with Citations**: Generated answers include citations back to specific chunks/pages
- **Hybrid Filtering**: Combine semantic search with metadata filters (year range, subject, document type)

---

## Current Status

### Implemented

| Module | Status |
|---|---|
| PDF extraction (pymupdf4llm) | Done |
| Document-aware chunking | Done |
| FastAPI backend (dev endpoints) | Done |
| Chunk viewer dev tool | Done |
| Tests (22 passing) | Done |

### In Progress / Planned

| Module | Status |
|---|---|
| Embedding pipeline (fastembed) | Planned |
| Vector index (pgvector in Postgres) | Planned |
| Hybrid search (semantic + metadata) | Planned |
| Answer generation with citations | Planned |
| PDF highlight annotation | Planned |

---

## Production Vision

### Platforms

| Platform | Account Required | Processing | Offline |
|---|---|---|---|
| Windows | Optional | Local | Yes |
| macOS | Optional | Local | Yes |
| Android | Yes | Cloud | No |
| iOS | Yes | Cloud | No |
| Web | Yes | Cloud | No |

### How It Works

**Desktop (primary)**:
- Install the app — no Docker, no configuration
- Upload PDFs — processed locally (extraction, chunking, embedding)
- Search works offline
- Optional: Sign in to sync data to cloud (access from mobile)

**Mobile / Web**:
- Sign in to your account
- PDFs processed by desktop appear automatically
- Search and view highlighted passages

**Data flow**:
```
Desktop (processing)      Cloud (sync)       Mobile/Web (viewing)
    ┌─────────┐           ┌────────┐          ┌─────────┐
    │ Extract │ ───────>  │ Supabase│ <──────  │ Search  │
    │ Chunk   │           │ Postgres│          │ View    │
    │ Embed   │           │ pgvector│          │ Highlight│
    └─────────┘           └────────┘          └─────────┘
```

---

## Getting Started (Development)

### Prerequisites

- Python 3.14+
- pip

### Installation

```bash
git clone https://github.com/Apoorv012/QueryNest-New.git
cd QueryNest-New

python -m venv .venv
.venv\Scripts\activate    # Windows
source .venv/bin/activate # macOS/Linux

pip install -r requirements.txt
```

### Running

```bash
# Run the full pipeline (ingest sample PDF)
python -m core.main

# Ingest a specific PDF
python -m core.main ingest <pdf_path>

# Run the dev server
uvicorn core.api.main:app --reload
```

### Chunk Viewer (Dev Tool)

```bash
cd tools/chunk-viewer
npm install
npm run dev
```

Opens at `http://localhost:5173`. Upload a PDF to inspect extraction and chunking output.

---

## Testing

Tests use pytest with a real PDF fixture ("Attention Is All You Need"):

```bash
pytest              # Run all tests
pytest -v           # Verbose output
pytest tests/chunking/test_chunker.py  # Single file
```

---

## Project Structure

```
QueryNest-New/
├── core/                    # Python engine
│   ├── ingest/              # PDF extraction (pymupdf4llm)
│   ├── chunking/            # Document-aware chunking
│   ├── models/              # Data models
│   ├── api/                 # FastAPI backend (dev)
│   └── main.py              # CLI entry point
├── tools/
│   └── chunk-viewer/        # Dev tool for inspecting output
├── tests/                   # Test suite
├── docs/                    # Architecture decisions, improvements
└── requirements.txt
```

---

## Architecture Decisions

See [docs/decisions.md](docs/decisions.md) for architectural decisions with rationale.

- **D1**: Document-aware chunking (heading-based)
- **D2**: pgvector in Supabase for storage
- **D3**: Platform split (desktop offline/cloud, mobile/web cloud-only)

---

## Contributing

Contributions welcome! Please open an issue first to discuss changes.

---

## License

This project is under active development. License TBD.
