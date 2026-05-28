# 🪶 QueryNest

**QueryNest** is a local-first, AI-powered document search engine that lets users find information inside their personal PDFs using natural language — with precise in-document highlights.

Instead of searching by file name, QueryNest understands the *meaning* of your documents. Search for "operating system concepts" and find every paper that discusses operating systems — even if those exact words never appear. Filter by year, exam type, or subject, and jump straight to the highlighted passage.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🔍 **Semantic Search** | Find documents by meaning, not keywords. Search "memory management" to find papers about RAM, paging, virtual memory, etc. |
| 📅 **Smart Filters** | Query by year range ("2020–2024"), recency ("last 3 years"), or exam type ("T1 only"). |
| 🖍️ **In-Document Highlighting** | Relevant passages are highlighted directly in the PDF with configurable colors. |
| 🔒 **Privacy-First** | Choose between fully local processing (embeddings + storage on your device) or optional cloud compute. |
| 📱 **Cross-Platform** | Android, iOS, Web, and Desktop clients — all powered by the same core engine. |

---

## 🏗️ Architecture

QueryNest follows a modular **monorepo** structure with a shared Python core and platform-specific frontends:

```
QueryNest-New/
├── core/                    # Shared Python engine (the brain)
│   ├── ingest/              # PDF loading, text extraction, normalization, cleanup
│   ├── chunking/            # Semantic chunking with heading detection
│   ├── embedding/           # Vector embedding generation (local & cloud)
│   ├── index/               # Vector index (FAISS / Hnswlib)
│   ├── search/              # Semantic search + metadata filtering
│   ├── storage/             # Document & chunk metadata persistence
│   ├── models/              # Shared data models (TextBlock, Chunk, etc.)
│   ├── config.py            # Global configuration
│   └── main.py              # CLI entry point
├── apps/                    # Platform-specific frontends
│   ├── web/                 # Web app (React / Next.js)
│   ├── mobile/              # Mobile app (React Native / Flutter)
│   └── desktop/             # Desktop app (Electron / Tauri)
├── packages/                # Shared frontend utilities
├── scripts/                 # Dev & deployment scripts
├── tests/                   # Test suite
│   ├── fixtures/            # Sample PDFs for testing
│   └── ingest/              # Ingest module tests
└── requirements.txt         # Python dependencies
```

### Core Pipeline

```mermaid
graph TD
    A["PDF File"] --> B["Ingest (PyMuPDF)"]
    B --> C["Chunking (Semantic)"]
    C --> D["Embedding (Local/Cloud)"]
    D --> E["Index (FAISS/Hnsw)"]
    E --> F["Search (Semantic + Filters)"]
    F --> G["Highlight (PDF Annot)"]
```

## 📦 Current Status

### ✅ Completed — Ingest & Chunking Pipeline

| Module | File | Status |
|---|---|---|
| **PDF Loader** | `core/ingest/loader.py` | ✅ Done |
| **Text Extractor** | `core/ingest/extractor.py` | ✅ Done |
| **Span → Line Normalizer** | `core/ingest/normalizer.py` | ✅ Done |
| **Line → Paragraph Normalizer** | `core/ingest/normalizer.py` | ✅ Done |
| **Header/Footer Cleanup** | `core/ingest/cleanup.py` | ✅ Done |
| **Heading Detection** | `core/chunking/heading.py` | ✅ Done |
| **Token Estimation** | `core/chunking/tokenizer.py` | ✅ Done |
| **Semantic Chunker** | `core/chunking/chunker.py` | ✅ Done |
| **TextBlock Model** | `core/models/text_block.py` | ✅ Done |
| **Chunk Model** | `core/models/chunk.py` | ✅ Done |

### 🔲 Upcoming — Core Engine

| Module | Status |
|---|---|
| Embedding generation (sentence-transformers) | 🔲 Next |
| Vector indexing (FAISS) | 🔲 Planned |
| Semantic search with metadata filtering | 🔲 Planned |
| Document metadata extraction (year, subject, type) | 🔲 Planned |
| PDF highlight annotation | 🔲 Planned |
| Storage layer (SQLite) | 🔲 Planned |
| REST API server | 🔲 Planned |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/Apoorv012/QueryNest-New.git
cd QueryNest-New

# Create virtual environment
python -m venv .venv

# Activate it
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Running

```bash
# Run the main pipeline (ingest + chunk a sample PDF)
python -m core.main

# Run tests
pytest
```

---

## 🧪 Testing

Tests are written with **pytest** and live in the `tests/` directory. The test suite uses the "Attention Is All You Need" paper (`tests/fixtures/sample.pdf`) as a fixture.

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/ingest/test_extractor.py
```

---

## 🔮 Roadmap

### Phase 1 — Core Engine (Current)
- [x] PDF ingestion & text extraction
- [x] Text normalization (span → line → paragraph)
- [x] Header/footer/junk removal
- [x] Semantic chunking with heading boundaries
- [ ] Embedding generation (sentence-transformers, local-first)
- [ ] Vector index (FAISS) for fast similarity search
- [ ] Semantic search with year/type/subject filters
- [ ] Document metadata extraction
- [ ] Storage layer (SQLite for metadata, FAISS for vectors)

### Phase 2 — Highlighting & API
- [ ] PDF highlight annotations on search results
- [ ] REST API server (FastAPI)
- [ ] Configurable highlight colors

### Phase 3 — Frontends
- [ ] Web app
- [ ] Android & iOS app
- [ ] Desktop app (Electron/Tauri)

### Phase 4 — Privacy & Deployment
- [ ] Cloud vs. local compute toggle
- [ ] End-to-end encryption for cloud mode
- [ ] Self-hosted deployment option

---

## 🛡️ Privacy Philosophy

QueryNest is built **local-first**. By default:
- All PDF processing happens on your device
- Embeddings are generated locally using open-source models
- No data leaves your machine

For users who want faster processing, an **optional cloud mode** is available — with data encrypted in transit and at rest.

---

## 📄 License

This project is under active development. License TBD.

---

## 🤝 Contributing

Contributions welcome! Please open an issue first to discuss what you'd like to change.