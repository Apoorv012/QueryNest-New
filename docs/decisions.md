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

---

## D4: Embedding Model — fastembed with BAAI/bge-small-en-v1.5

**Decision:** Use fastembed library with BAAI/bge-small-en-v1.5 model for text embeddings.

**Why:**
- **Size**: 67 MB (smallest available), no PyTorch dependency
- **Speed**: ONNX Runtime optimized for CPU inference
- **Quality**: Good on MTEB leaderboard, sufficient for personal PDF search
- **License**: MIT (permissive)
- **Dimensions**: 384 (fast vector search)
- **Already in requirements.txt**: No new dependencies needed

**Alternatives considered:**
- sentence-transformers: 2GB+ install (PyTorch), overkill for this use case
- Larger BGE models (bge-base, bge-large): Higher quality but 3-18x larger
- API models (OpenAI, Cohere): Not free, requires API key, contradicts local-first

**Risk:** English-only model. Mitigated by future upgrade path to multilingual models if needed.

**Future considerations:**
- If quality insufficient, upgrade to BAAI/bge-base-en-v1.5 (210 MB, 768 dims)
- If multilingual needed, upgrade to intfloat/multilingual-e5-large (2.2 GB)

---

## D5: Date Extraction — Fallback Chain (User Input → Filename → Metadata → Content → Null)

**Decision:** Resolve a document's date through an ordered fallback chain, stopping at the first source that yields a confident result: explicit user input, then a 4-digit year in the filename, then the PDF's `creationDate`/`modDate` metadata, then a date-like phrase in the first-page text, then `null` if nothing matches. Implemented in `core/ingest/date_extractor.py`; `extract_date()` also returns which source won (`"filename"`, `"metadata"`, `"content"`, or `None`) so callers (e.g. the bulk upload job status) can surface provenance to the user.

**Why:**
- **User input first**: a human-provided date is always more trustworthy than anything inferred, and should never be overridden by a heuristic.
- **Filename next**: personal PDF collections are frequently named with a year (`report_2023.pdf`, `2020-audit.pdf`) — cheap, fast, and reasonably reliable regex match on `\d{4}`.
- **Metadata next**: `creationDate`/`modDate` are structured and unambiguous when present, but many PDFs (scanned documents, exports) have stripped or inaccurate metadata, so it's tried only after the cheaper filename check.
- **Content last**: regex-scanning the first page for phrases like "published in 2020" or "Copyright 2019" is the most expensive and least reliable signal (false positives from citation years, etc.), so it's the last resort before giving up.
- **Null is a valid outcome**: search and document listing already treat `document_date: None` as "unknown" rather than crashing or defaulting to today — no forced guess.

**Alternatives considered:**
- LLM-based date extraction: higher accuracy on ambiguous content, but adds API cost/latency to every upload and a network dependency, contradicting the local-first bulk-upload path.
- Metadata-only: simplest, but unreliable — many real-world PDFs have missing or wrong `creationDate`.
- Always require user input: most accurate, but adds friction to bulk upload where users are uploading many files at once.

**Risk:** Filename year and content-year regexes can pick up an unrelated 4-digit number (a page count, a citation year, an ID). Mitigated by checking sources in order of reliability and by exposing `date_source` so a wrong guess is visible and user-correctable via `PATCH /documents/{doc_id}/date`.

---

## D6: NL Query Date Parsing — Regex-Based

**Decision:** Extract date-range expressions from search queries with hand-written regex patterns (`core/query/parser.py`) rather than an LLM or NLP library, covering relative ranges ("last 3 years", "past 6 months"), exact years ("in 2020"), inclusive ranges ("from 2020 to 2023", "2020-2023"), and open bounds ("before 2020", "after 2020"). `parse_query()` returns a `ParsedQuery` with the date phrase stripped from the query text plus `date_from`/`date_to`, which the search route feeds into the vector store as a SQL pre-filter alongside the semantic query.

**Why:**
- **No API dependency**: runs entirely in-process, no external call or API key, consistent with the local-first, low-dependency posture of the rest of the pipeline (D3, D4).
- **Deterministic and testable**: a fixed set of regex patterns is easy to unit test exhaustively (`tests/query/test_parser.py`) and behaves the same way every time, unlike an LLM's variable output.
- **Fast**: negligible latency added to every search request — regex matching is microseconds versus a network round-trip for an LLM call.
- **Covers the realistic query vocabulary**: personal PDF search queries use a small, predictable set of date phrasings; a comprehensive NLP date parser (e.g. `dateparser`) would handle more phrasings but adds a dependency for cases unlikely to occur in practice.

**Alternatives considered:**
- LLM-based query understanding: more flexible phrasing support, but adds latency, cost, and a hard dependency on an external API for a core search-path operation.
- General-purpose date-parsing library (e.g. `dateparser`, `dateutil`): broader coverage, but pulls in a new dependency for marginal gain over the query vocabulary actually seen.
- No date parsing (metadata filters only via UI controls): simpler, but loses the "just type it in the search box" ergonomics of combining semantic and date intent in one query.

**Risk:** Regex patterns only cover the phrasings they were written for — an unanticipated phrasing (e.g. "since March") silently falls through to `ParsedQuery(query=query)` with no date filter, rather than erroring. Mitigated by keeping the query text unmodified in that case, so the search simply falls back to pure semantic search instead of failing.

---

## D7: Corpus Scope — Three Document Families, All Digital-Native

**Decision:** The eval corpus spans academic papers, short financial documents, and
career/study documents (job descriptions, hiring brochures, assignments).

**Why:** "Question papers" were dropped — the available ones are scanned images, and OCR is a
separate project. `eval.pdf` in the candidate set proved the point: 3 pages, **2 characters of
extractable text**. Career/study documents replace them: digital-native, genuinely what sits in
a student's Downloads folder or WhatsApp chat, and structurally varied enough to be
discriminating.

**Risk:** The career family is thematically narrow — several job descriptions read similarly, so
queries must be written carefully to be discriminating rather than ambiguous.

---

## D8: Under-Filled Date-Filtered Results Are Backfilled

**Decision:** When a date-filtered search returns fewer than `top_k` results, run a second
unfiltered search and append the remainder, marked `within_date_range: false`.

**Why:** A date expression in a natural-language query is a hint, not a hard constraint. A user
who types "insurance policy from last year" and receives 2 results is worse served than one who
receives those 2 plus 3 near-misses they can judge themselves.

**Risk:** Silently mixing in-range and out-of-range results would make the date filter feel
broken. Mitigated by the explicit `within_date_range` flag on every result, which the UI must
render as a visible divider.

---

## D9: Undated Documents Are Not Excluded by Date Filters

**Decision:** Date filters use `(document_date IS NULL OR document_date >= %s)` rather than a
bare comparison.

**Why:** SQL `NULL >= x` evaluates false, so every document whose date extraction fell through
to `null` silently disappeared from any date-filtered search. D5 treats `null` as a legitimate
outcome, so it must not also be a disqualifier. Measured relevance: 7 of the 17 corpus
documents currently have no detectable date.

---

## D10: Corpus Documents Are Capped at ~45 Pages

**Decision:** No eval-corpus document exceeds ~45 pages.

**Why:** Representativeness — QueryNest targets general public use, and a 344-page annual report
is not a document its users own. And iteration speed: the excluded documents were 88% of
extraction cost, and removing them took a full re-seed from ~23 minutes to ~3.5, which is what
makes per-change retrieval measurement affordable.

**Risk:** The financial family is reduced to two Berkshire filings, which is too thin to support
a "works on financial documents" claim. Short financial documents (quarterly reports, 10-Q
filings, fund factsheets) are still needed.

---

## D11: Vector Index — HNSW, Not IVFFlat

**Decision:** Use HNSW for the embedding index.

**Why:** IVFFlat learns its centroids from the rows present at index-build time, and `setup()`
runs against an empty table. The resulting index was degenerate: with the default
`ivfflat.probes = 1`, queries returned **zero rows**. HNSW builds incrementally as rows are
inserted and cannot reach that state. Switching moved Recall@5 from 0.5944 to 0.9444 with no
other change. Full analysis in `improvements.md`.

**Alternatives considered:**
- Keep IVFFlat and rebuild the index after ingest: works, but adds a fragile ordering
  requirement (every bulk load must be followed by a REINDEX) whose omission fails silently.
- Keep IVFFlat and raise `ivfflat.probes`: restores results but scans most lists, forfeiting the
  point of the index.

**Risk:** HNSW indexes are slower to build and use more memory than IVFFlat. At personal-library
scale this is immaterial; revisit only if index build time becomes noticeable.
