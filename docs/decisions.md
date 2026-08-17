# Decisions

Architecture and technical decisions with rationale.

---

## D1: Chunking Strategy — Document-Aware (Heading-Based)

**Decision:** Use pymupdf4llm's `section-header` blocks as boundaries. Group consecutive blocks under a heading into one chunk, flush on next heading or token limit overflow.

**Why:** Academic papers have clear, predictable heading hierarchies ("1 Introduction", "3.1 Encoder", etc.). pymupdf4llm already classifies these as `section-header` blocks — no custom heading detection needed. Paragraphs under a heading are topically coherent, and bounding boxes are preserved for highlight rendering.

**Alternatives considered:**
- Fixed-size splitting: breaks context mid-sentence, no structural understanding.
- Semantic chunking (embed → merge similar consecutive paragraphs): marginal gain for this domain, adds embedding latency at ingestion time, threshold tuning required.
- Paragraph-level only: variable sizes (2 words to 200+), tiny chunks produce poor embeddings.

**Risk:** Some sections may be very large (e.g., full "Related Work" chapter). Mitigated by a token overflow flush within sections — split at paragraph boundaries when a section exceeds the token limit.

---

## D2: Storage Strategy — pgvector in Supabase Postgres

**Decision:** Use pgvector extension in Supabase Postgres for vector storage and metadata.

**Why:** 
- pgvector integrates directly into Postgres — no separate vector database to manage
- Supabase provides hosted Postgres with pgvector built-in, reducing infrastructure overhead
- Same SQL query handles both vector search and metadata filtering (year, subject, type)
- Row-level security (RLS) enables per-user data isolation
- Local development can use same Postgres setup (Docker or native install)

**Alternatives considered:**
- FAISS: Standalone index file, no metadata filtering, no multi-user support
- ChromaDB: Additional dependency, less mature ecosystem
- Pinecone/Weaviate: Cloud-only, vendor lock-in, unnecessary for personal/small-scale use

**Risk:** Requires Postgres installation for local development. Mitigated by Docker one-liner for dev and Supabase for production.

---

## D3: Platform Split — Desktop Offline/Cloud, Mobile/Web Cloud-Only

**Decision:** Desktop apps support both offline (local Postgres) and cloud (Supabase) modes. Mobile and web apps are cloud-only.

**Why:**
- Desktop has sufficient CPU/RAM for local Postgres and heavy processing (PyMuPDF4LLM, fastembed)
- Mobile/web cannot efficiently run Python-based extraction/embedding pipelines
- Desktop as "processing hub" makes sense — user processes PDFs locally, syncs to cloud for mobile access
- Offline mode preserves privacy for users who don't want cloud dependency
- Cloud mode enables cross-device access (desktop → mobile → web)

**Alternatives considered:**
- All-local: Mobile can't run Postgres or Python processing efficiently
- All-cloud: Requires internet, contradicts local-first privacy goal
- pglite: WASM-based, JS/TS only, alpha status, no Python binding

**Risk:** Sync between local and cloud adds complexity. Mitigated by making sync optional and treating cloud as secondary storage.
