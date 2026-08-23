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

---

## D12: Date Filtering Is Served as Three Tiers, Not Two

**Decision:** A date-filtered search is served as three successive tiers, in descending order of
confidence, topping up until `top_k` is reached:

1. **`in_range`** — the document has a date, and it falls inside the requested range.
2. **`undated`** — the document has no detectable date, so it *might* match.
3. **`out_of_range`** — the document has a date, and it falls outside the range.

Each result carries a `date_match` field naming its tier. This supersedes the boolean
`within_date_range` introduced with D8.

**Why:** D9 admitted undated documents by widening the predicate to
`(document_date IS NULL OR document_date >= %s)`. That fixed the disappearance problem but
created a subtler one: undated documents were mixed into the top tier and reported as
`within_date_range: true` — asserting a match the system never verified. **7 of the 17 corpus
documents have no detectable date**, so this was the common case, not an edge case.

The three tiers encode what is actually known. An undated document might be the one the user
wants. A document dated 2019 when the user asked for 2023 is a *verified* non-match. "Unknown"
therefore belongs above "known wrong", and a two-state flag cannot express that ordering.

**Tier order beats similarity score**, deliberately: a high-scoring out-of-range document ranks
below a lower-scoring in-range one. The date expression is treated as a strong preference rather
than either a hard filter or a mere tiebreak.

**Alternatives considered:**
- *Hard filter (no backfill):* a user typing "last year" who gets 2 results is worse served than
  one who gets 2 plus near-misses they can judge. Rejected as D8.
- *Two tiers (in-range, then everything else):* the previous behaviour. Simpler, but collapses
  "unknown" and "known wrong" — losing exactly the distinction a user needs to judge a result.
- *Boost rather than tier:* blend a date-proximity term into the similarity score. Rejected as
  untunable without a much larger temporal query set, and it makes results hard to explain.

**Implementation note:** the three tier predicates are mutually exclusive in SQL
(`IS NULL` / `IS NOT NULL` + `>=,<=` / `IS NOT NULL` + `<,>`), so tier results concatenate
without de-duplication. Each tier requests only the shortfall (`top_k - len(results)`), and
later tiers are skipped entirely once `top_k` is met. The route stamps `date_match` itself
rather than trusting the store, so the label cannot drift per implementation.

## D13: Drop Unusably Tiny Chunks at Ingest

**Decision:** After chunking, discard any chunk whose estimated token count falls below
`DROP_BELOW_TOKENS = 20` (`core/chunking/chunker.py`). If every chunk in a document is below
the threshold, the document is kept unfiltered rather than emptied.

**Why:** a `section-header` block flushes the current chunk and then becomes the first block of
the next one, so two consecutive headings emit a chunk whose entire content is the first
heading — `"4 Results"`, `"E Additional Details"`, `"APPENDIX"`. At 2-3 tokens these embed to a
vague near-centroid vector sitting at middling distance from *every* query, so they surfaced as
plausible-looking noise: measured ranks 3 and 6 for the query "job descriptions", ahead of three
actual job descriptions, from an AI paper and a RAG paper whose section headers happened to
collide with the query's vocabulary.

**Alternatives considered:**
- *Merge into a neighbouring chunk instead of dropping:* tried first, but folding a tiny chunk
  into its neighbour also moved that neighbour's boundaries, which cost document-level recall
  on chunks that were fine on their own. Dropping touches only the unusable chunk.
- *Filter at query time instead of ingest time:* rejected — a chunk that can never be a useful
  result shouldn't occupy an index slot, an HNSW graph node, and a per-result check forever.
- *Raise MIN_TOKENS instead of adding a second threshold:* `MIN_TOKENS = 120` governs when the
  *chunker* flushes early to avoid a tiny chunk mid-document; it doesn't apply to the trailing
  chunk after the last heading, which is where this failure mode actually occurs. The two
  thresholds serve different points in the pipeline and are deliberately kept separate.

**Risk:** the dropped chunk's text isn't lost — it's already stored separately as the *next*
chunk's `Chunk.heading` — so this is a pure precision gain with no coverage cost, confirmed by
eval (nothing regressed; see `docs/plan.md` §6).

## D14: Normalize Per-Document Metadata into a `documents` Table; Add Content-Hash Dedup

**Decision:** Split `chunks` into two tables. `documents` (one row per document: `document_id`
PK, `user_id`, `filename`, `document_date`, `content_hash`, `page_count`, `chunk_count`) now
owns everything that used to be repeated on every chunk row; `chunks` keeps only per-chunk data
(`document_id` FK, `chunk_index`, `text`, `heading`, `embedding`, `page`, `source_blocks`).
`documents (user_id, content_hash)` carries a partial unique index (`WHERE content_hash IS NOT
NULL`), and `POST /upload/bulk` SHA-256-hashes each upload before extraction, short-circuiting
to the existing `document_id` on a match instead of re-extracting, re-chunking, and re-embedding.

**Why:** `filename`, `user_id`, and `document_date` were duplicated on every chunk row, so
re-dating a document meant rewriting all of its chunks, and there was nowhere to hang
document-level metadata like a content hash without duplicating it across every row too.
Extraction is ~77% of ingest cost at roughly 1,790 ms/page, so deduplicating on content hash is
the highest-leverage remaining performance win in the ingest path: it removes work rather than
rearranging it (the same reasoning that ruled out ingest parallelism — see `docs/plan.md` §3).

**Migration is the risky part, so it's written as an explicit, re-runnable step
(`_migrate_document_metadata` in `core/index/pgvector.py`), run from `setup()` but distinct from
its `ADD COLUMN IF NOT EXISTS` calls.** It backfills `documents` from `SELECT ... GROUP BY
document_id` over the existing `chunks` rows — `MIN()` over each column, since a document's rows
all share the same metadata — and only *then* drops the now-duplicated columns off `chunks`.
`ADD COLUMN IF NOT EXISTS` is safely idempotent; a column *drop* is not, so getting the ordering
wrong risks losing metadata irrecoverably. The migration checks for the old `chunks.user_id`
column first and is a no-op once it's gone.

**Content_hash is nullable, and the unique index is partial**, because documents ingested before
this change has no hash and fabricating one would be worse than admitting it. Every new ingest
sets it, so dedup holds going forward without requiring a backfill of historical rows.

**Consequence:** any query needing `user_id` (e.g. the BM25 baseline's `WHERE user_id = %s`) now
joins `chunks` to `documents`. `SearchResult` gained a `filename` field, populated from the join
so callers don't need a second lookup to display which file a result came from.

**Verified against the existing eval baseline** — the join changes only where `user_id` lives,
not which rows match, so retrieval metrics were confirmed unchanged before shipping.

Supersedes the schema shown in earlier drafts of `docs/ARCHITECTURE.md`, where `chunks` carried
`user_id`, `filename`, and `document_date` directly.

**Risk:** the UI must render the tier boundaries visibly. Silently mixing tiers would make the
date filter feel broken — which is the same failure D8 warned about, now with three groups.

---

## D15: Public Demo Backend Is a Separate App, Not an Auth Flag

**Decision:** The internet-facing demo (`querynest.apoorvm.com`) is served by `core/api/public_main.py`,
a second, independent `FastAPI()` instance that mounts only three routers — `health`,
`public_search`, `public_documents`. It is not `core/api/main.py` with a "public mode" flag that
disables routes at runtime.

**Why:** A flag-based lockdown means every future route added to the full backend is public by
default unless someone remembers to gate it — the failure mode is silent and grows over time. A
separate app that simply never imports `upload.py` or `eval.py` cannot serve them regardless of
what changes elsewhere; there is no flag to forget. `public_search.py`'s `/search` also accepts no
`user_id` field from the client at all (rather than accepting one and validating it equals
`golden_user`), for the same reason — the golden-only behavior is structural, not a checked
invariant.

**Alternatives considered:**
- Add an admin-key header requirement to the existing app's write routes, deploy that app
  publicly: considered and initially built, then reverted — it still means the full ingest/eval
  code path is reachable from the internet (just behind a header check), and every new sensitive
  route added later needs the same header dependency remembered and applied correctly.
- Feature-flag routes at include-time (`if public_mode: skip upload_router`): closer to the chosen
  design, but still one shared codebase with a runtime branch, versus two entrypoints where the
  absence of imports is the guarantee.

**Consequence:** the full backend (`main.py`) and `tools/dev-dashboard` are never deployed at all
— they run locally against the same Supabase project for ingest, eval-seeding, and admin
inspection. Reseeding the public demo corpus means running `/eval/seed` locally, not against the
deployed API.

**Risk:** two FastAPI apps means some route logic (e.g. the tiered date-filtered search in
`search.py`) is duplicated rather than shared, since `public_search.py` reuses `search.py`'s
`_first_per_document`/`OVERFETCH_FACTOR` helpers by import but reimplements the route body. Judged
acceptable at this scale — the alternative (a shared route function parameterized by
auth-vs-public) would reintroduce the flag-based coupling this decision exists to avoid.

---

## D16: PDF Storage Gets the Same Local/Hosted Split as the Vector Store

**Decision:** `core/storage/` defines a `FileStore` ABC (`save`, `get`, `delete`, `delete_all`)
with `LocalFileStore` (disk, `data/uploads/`) and `SupabaseFileStore` (Supabase Storage REST API)
implementations, picked by `get_file_store()` off the same `QUERYNEST_STORAGE_MODE` env var
`core/index/config.py` already uses for the database. `upload.py` and `documents.py` now call
`file_store.save(...)`/`.get(...)` instead of `Path.write_bytes()`/`FileResponse(pdf_path)`
directly.

**Why:** PDFs were written straight to local disk regardless of `QUERYNEST_STORAGE_MODE`, which
works for local development but not for a backend deployed to Render — Render's filesystem is
ephemeral, so anything written to disk disappears on the next deploy or restart. The public demo
needs the PDF bytes to persist independently of the container. Mirroring the existing
`VectorStore` split (one interface, one local implementation, one hosted implementation, same
config switch) keeps the two storage concerns consistent rather than inventing a second pattern.

`SupabaseFileStore` calls the Storage REST API directly via `requests` (already a dependency)
rather than adding the `supabase-py` SDK — the surface needed is three calls (upload, sign-url,
delete), which doesn't justify a new dependency.

**Alternatives considered:**
- S3 (or S3-compatible) storage via `boto3`: viable, but adds a new dependency and a second cloud
  account to manage, when the project already runs entirely on Supabase (Postgres + Storage in one
  project, one set of credentials).
- Keep local disk and give the Render container a persistent volume: Render's free tier doesn't
  offer one; even on a paid tier, this ties the demo's data to a specific container instance
  rather than the same Supabase project the local admin backend already writes to.

**Risk:** `SupabaseFileStore.get()` returns a signed URL (`str`) while `LocalFileStore.get()`
returns raw bytes — the two branches of the ABC's return type are genuinely different shapes, so
every caller (`documents.py`, `public_documents.py`) must branch on `isinstance(result, str)`
rather than treating the interface as fully uniform. Judged acceptable: forcing local mode to
also return a URL (e.g. a `file://` path or a local static-file route) would add complexity to the
common local-dev path to preserve a uniformity the caller-side branch already handles cleanly in
two lines.
