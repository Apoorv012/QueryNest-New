# QueryNest v2 — Execution Plan

Status: proposed, 2026-08-20. Supersedes nothing; complements `decisions.md`.

---

## 0. Product goal (the thing every decision serves)

People accumulate PDFs in WhatsApp chats and their Downloads folder. When they need one
back, they search by **filename** — and filenames are useless (`doc_20231104_final(2).pdf`).
So they scroll, open files at random, and usually give up.

QueryNest lets them **search by what's inside the document**, in plain language, optionally
scoped by time ("insurance policy from last year"), and jump straight to the highlighted
passage.

**The competitor is filename search** — that is what users do today, and it is the problem
statement. It is *not* the measurement baseline: see Phase 1.4 for why (its score is set by how
files happen to be named, so it can be authored rather than measured). Retrieval quality is
measured against **BM25**.

### Target user journey

1. Upload PDFs (bulk, background).
2. Search in natural language, optionally with a date/time expression.
3. Get an AI-generated answer with citations (Google AI-mode style).
4. See the matching documents ranked, with their dates.
5. Click a citation or a document → PDF opens with the passage highlighted.

Steps 1, 2 and 4 exist today. Steps 3 and 5 are Phase 4.

---

## 1. Scope decisions (locked — do not re-litigate mid-build)

### D7: Corpus scope — three document families, all digital-native

| Family | Examples | Tests |
|---|---|---|
| Academic papers | arXiv PDFs (current fixtures) | Conceptual retrieval, dense prose |
| Financial/corporate reports | Annual reports, audits (current fixtures) | Numeric + **table** retrieval |
| Personal admin documents | Invoices, bank/card statements, insurance policies, school circulars, warranty cards, tickets | Short docs, heavy metadata, dates that actually matter |

**Rationale.** "Question papers" was dropped because they are almost always scanned images,
and OCR is a separate project. Personal admin documents replace them: they are digital-native,
they are *literally what sits in a WhatsApp chat or Downloads folder*, and they exercise date
filtering far better than academic papers do. Keeping three families preserves the
"generic, not just for researchers" claim.

**Annual reports stay in scope**, which means table extraction must be fixed (Phase 2.4).
Dropping them would narrow the product to academics and defeat the goal.

### D10: Corpus documents are capped at ~45 pages

**Decision.** No document in the eval corpus exceeds ~45 pages. Full annual reports
(`gsk_2024` 344pp, `unilever_2024` 305pp, `ppl_2024` 170pp, `berkshire_2024` 150pp) and
`gpt3_2020` (75pp) are excluded. `chain_of_thought_2022` (43pp) is kept as a deliberate
borderline case.

**Why:**
- **Representativeness.** QueryNest targets general public use — the PDFs in a Downloads folder
  or a WhatsApp chat. A 344-page annual report is not that document, so tuning retrieval
  against it optimizes for a user who does not exist.
- **Iteration speed, which turns out to be the bigger win.** The four largest reports were 1,087
  of 1,228 corpus pages — 88% of extraction cost for 4 of 14 documents. The cap takes a full
  re-seed from **~23 minutes to ~3.5**, which is what makes Phase 2's "change one thing, re-run
  the eval" discipline actually affordable. Before the cap, strict per-change attribution would
  have cost an hour per change and would have been abandoned in practice.
- Financial documents remain in scope; they are simply represented by short filings rather than
  complete annual reports.

**Consequence — the golden set must be rebuilt.** The cap kills 11 of the current 30 queries
outright and degrades 6 more, leaving ~19 usable. This is less costly than it sounds: Phase 1.5
already required rewriting the golden set to reach 50 queries with ≥10 temporal ones. Retire the
dead queries rather than mourning them.

**Consequence — the financial family needs restocking.** Only `berkshire_2022` (10pp) and
`berkshire_2023` (16pp) survive. Short financial documents are needed: quarterly reports,
10-Q filings, small-company annual reports, fund factsheets — anything in the 10–30pp range that
is still table-heavy enough to exercise Phase 2.4.

> **Open — pending corpus review.** The third family is provisional. Candidate material on hand:
> invoices, and friends' resumes. Before locking this, assemble the candidate PDFs and check
> three things: (1) are they digital-native, not scanned? (2) do they carry a real date, so
> temporal queries are meaningful? (3) can 10+ non-trivial queries be written against them?
> Resumes are a weak fit — they are undated and near-identical in structure, so they exercise
> neither date filtering nor topical discrimination. Invoices and statements are a strong fit.
> If a viable third family cannot be assembled, the honest fallback is to ship two families and
> describe the scope accurately, rather than pad the corpus with documents nobody would search.

### D8: Under-filled date-filtered results — filter, then backfill

When a date-filtered search returns fewer than `top_k` results, run a second unfiltered
search and append the remainder, clearly marked as outside the requested range.

**Rationale.** A date expression is a hint, not a hard constraint. A user who types "last
year" and gets 2 results is worse off than one who gets 2 in-range results plus 3 near-misses
they can judge for themselves.

**Constraint:** backfilled results must be visually and structurally distinguishable — a
`within_date_range: bool` on each result, and a divider in the UI. Silently mixing them
would make the date filter feel broken.

### D9: Undated documents are not excluded by date filters

`document_date IS NULL` currently makes a document invisible to any date-filtered query
(SQL `NULL >= x` is false). Undated documents will instead be treated as backfill candidates
under D8, never as hard exclusions.

---

## 2. Storage: the answer is yes, Postgres — with one gap

**Keep pgvector on Postgres.** It is the right call for this product and should not be
revisited. At personal-library scale (thousands of documents, tens of thousands of chunks),
a dedicated vector database buys nothing and costs an extra service to run. One query does
both similarity search and metadata filtering, and Supabase gives it to you hosted.

**The real gap is not the vectors — it is the PDF bytes.** They are currently written to
`data/uploads/<user_id>/<doc_id>.pdf` on the API server's local disk. That is fine for one
developer and breaks the moment a second person uses it: the files do not survive a redeploy,
cannot be served from more than one machine, and the directory is attacker-controlled
(see Phase 0.1).

**Target layout:**

| Data | Where | Why |
|---|---|---|
| Chunks + embeddings + metadata | Postgres (pgvector) | Already correct |
| Document-level metadata | Postgres, new `documents` table | Currently duplicated on every chunk row |
| PDF bytes | Supabase Storage (object storage) | Durable, servable, already in your stack |
| Job progress | In-memory for now; Postgres when jobs must survive restarts | Acceptable debt, documented |

---

## 3. Phases

Each task lists **file**, **change**, and **acceptance criteria**. Work top to bottom;
Phase 1 gates Phase 2 because you cannot tune what you cannot measure.

---

### Phase 0 — Correctness and safety (blocking, ~half a day)

Nothing else ships until these land. These are bugs that silently corrupt data or expose files.

**0.1 — Path traversal via `user_id`**
- Files: `core/api/routes/documents.py`, `core/api/routes/upload.py`
- `GET /documents/{doc_id}/pdf?user_id=..` currently serves any `.pdf` on disk outside the
  upload directory (verified reproducing). The same unvalidated `user_id` reaches
  `mkdir(parents=True)` and `write_bytes` on upload.
- Change: validate `user_id` against `^[A-Za-z0-9_-]{1,64}$` in one shared dependency used by
  every route. Additionally `resolve()` the final path and assert it is inside `UPLOAD_DIR`
  before serving.
- Acceptance: a test asserting `user_id=".."`, `"../.."`, and `"a/../.."` all return 4xx and
  serve no bytes.

**0.2 — Silent indexing failure reported as success**
- File: `core/api/routes/upload.py:114`
- `except (RuntimeError, OSError): pass` swallows every embed/store failure and still marks the
  file `"done"`. Worse, `psycopg2.Error` is neither of those, so a DB error escapes both
  handlers and pins the job at `"pending"` forever.
- Change: catch `Exception`, record the error on the `FileStatus`, and introduce a distinct
  status `"indexed_partially"` (extracted and chunked, but not searchable) so the UI can tell
  the truth.
- Acceptance: with the DB unreachable, the job reaches a terminal state and the per-file status
  names the failure. No file ever reports `"done"` while unsearchable.

**0.3 — Undated documents dropped by date filters (implements D9)**
- File: `core/index/pgvector.py`
- Change: `(document_date IS NULL OR document_date >= %s)`, same for the upper bound.
- Acceptance: a document with `document_date = NULL` is returned by a date-filtered search.

**0.4 — Dependency hygiene**
- File: `requirements.txt` (+ new `requirements-dev.txt`)
- `requests` and `numpy` are imported but never declared (they work only transitively).
  Nothing is version-pinned. `httpx2` is correct and stays — Starlette 1.6 imports it directly
  and deprecates plain `httpx` — but it is test-only.
- Change: declare `requests` and `numpy`; pin every runtime dependency to a known-good version;
  move `pytest` and `httpx2` to `requirements-dev.txt`; update CI to install both.
- Acceptance: `pip install -r requirements.txt` in a clean venv runs the API; adding
  `-r requirements-dev.txt` runs the tests.

**0.5 — Page-index inconsistency**
- Files: `core/ingest/extractor.py`, `docs/ARCHITECTURE.md`
- `ExtractedPage.page_number` is 1-indexed while `ExtractedBlock.page` is 0-indexed, and the
  docs describe both as 0-indexed. This will produce an off-by-one in PDF highlighting (Phase 4).
- Change: make both 0-indexed, convert once at the display boundary, fix the docs.
- Acceptance: a test asserting `doc.pages[0].page_number == 0` and that every block on that page
  reports `page == 0`.

---

### Phase 1 — An evaluation you can defend in an interview (~1–2 days)

This is the phase that produces the resume numbers. **The current metrics are wrong** and will
not survive scrutiny from anyone who knows IR — which is exactly who reads that resume line.

**1.1 — Fix `recall_at_k`**
- File: `core/eval/metrics.py:14`
- Relevance is judged per *document*, but the runner passes one entry per retrieved *chunk*.
  Duplicates inflate the numerator against a set-sized denominator, so recall can exceed 1.0
  (verified: an 8+2 chunk split over 2 relevant docs yields `recall@10 == 5.0`).
- Change: deduplicate to document level in the runner (first occurrence wins, rank preserved),
  and guard `metrics.py` with `min(hits / len(relevant), 1.0)` as a defensive backstop.
- Acceptance: a unit test asserting recall is always in `[0, 1]` given duplicate input.

**1.2 — Fix `ndcg_at_k`**
- File: `core/eval/metrics.py:32`
- IDCG is computed from `sorted(retrieved_relevances)` instead of from the golden set's ideal
  ranking, so any result set returned in descending order scores exactly 1.0 — including one
  where every hit is merely "somewhat relevant" (verified: `ndcg_at_k([1]*10, 10) == 1.0`).
- Change: `ndcg_at_k(relevances, ideal_relevances, k)` — the caller supplies the true ideal
  from `expected_docs`.
- Acceptance: `ndcg_at_k([1]*10, [2,2,1,...], 10) < 1.0`.

**1.3 — Evaluate at document level, and say so**
- File: `core/eval/runner.py`
- Decision: **document-level**. Rationale: it matches the user's actual goal ("find me the
  file"), it matches how the golden set is already annotated, and it needs no re-annotation.
  Chunk-level is more informative but requires labelling chunk ids, which will churn every time
  chunking parameters change — a trap during Phase 2.
- Change: dedupe retrieved documents preserving rank order before computing any metric.
  Document this choice in `docs/evaluation.md` so the numbers are interpretable.
- Acceptance: `retrieved_doc_filenames` contains no duplicates; report states "document-level".

**1.4 — Add the baseline that makes the numbers mean something**
- New file: `core/eval/baselines.py`
- A metric without a baseline is not an achievement.

**The baseline is BM25 over document content.** Classic keyword ranking (`rank_bm25`, or
Postgres `ts_rank`, which needs no new dependency). It is the standard IR baseline, it is what
a knowledgeable reader will expect, and — critically — **its score is a property of the corpus,
not a property of choices you made.**

> **Why filename search is *not* a valid baseline.** Its score is set entirely by how the
> fixtures happen to be named. Name them `attention_2017.pdf` and it scores well; name them
> `x.pdf, y.pdf, z.pdf` and it scores zero. That means any "N× better than filename search"
> figure is a number you *authored* by choosing filenames, not one you *measured*. It would not
> survive one follow-up question in an interview. Do not put it on a resume.

- Change: run semantic and BM25 over the same golden set; emit a comparison table.
- Acceptance: `python -m core.eval` prints semantic vs BM25 side by side, per query type.
- **Expect BM25 to win some queries** — exact identifiers, proper nouns, invoice numbers. That
  is the normal, well-documented result, and it is the empirical argument for true hybrid
  (BM25 + vector) retrieval later. Treat it as a finding, not a failure.
- **The resume line this produces:** *"Semantic PDF retrieval scoring 0.XX Recall@5 / 0.XX MRR
  on a 50-query golden set, +XX% over a BM25 keyword baseline."* Specific, falsifiable, and it
  shows you know what a baseline is — which is the actual signal being read for.

**1.4b — Filename findability as a *product* measurement (not a baseline)**
- The "filenames are useless" thesis is still worth quantifying — just as an observation about
  the real world rather than a retriever you benchmark against.
- Change: once real PDFs are collected from real Downloads/WhatsApp folders (uncurated, with
  whatever names they actually carry), measure what fraction are findable by filename alone.
- That number describes *the problem*, and because you did not choose those filenames, it is
  honest. Report it as motivation, never as the denominator of an improvement ratio.

**1.5 — Grow and rebalance the golden set**
- File: `data/eval/golden.json`
- Current: 30 queries, **zero temporal queries** — despite date filtering being the headline
  differentiator and the subject of three ADRs. Also 19 of 30 queries list the same filename
  twice, intending two passages, which document-level evaluation discards.
- Change: reach **50 queries** minimum. Add at least 10 temporal queries ("insurance policy
  from last year", "invoices from 2023", "papers before 2020"). Add queries over the new
  personal-admin fixtures. Remove duplicate `expected_docs` entries now that they are inert.
- Acceptance: ≥50 queries; ≥10 of `type: "temporal"`; every corpus family represented.

**1.6 — Make the harness trustworthy**
- File: `core/eval/runner.py`
- `run_search` has no `raise_for_status()`, so a 503 from a misconfigured API silently scores
  as zero — a setup failure indistinguishable from a retrieval failure. Latency also includes
  the HTTP round-trip and a cold ONNX model load on the first query.
- Change: raise on non-2xx; issue one discarded warmup query; report p50/p95 latency, not just
  the mean.
- Acceptance: a stopped API produces a clear error, not a report of all zeros.

**1.7 — Record the baseline**
- Run the full eval and commit the report. Every Phase 2 change is measured against this file.
- Acceptance: `reports/report_<ts>_<commit>.json` committed, referenced in `docs/evaluation.md`.

---

### Phase 2 — Retrieval quality (~1–2 days, measure after each step)

Change **one thing at a time** and re-run the eval. That discipline is also what makes the
resume claim defensible: you will be able to say *which* change bought *which* improvement.

**2.1 — Use the query prefix bge was trained with** *(expect the largest single gain)*
- File: `core/embedding/fastembed.py:56`
- `embed_query` calls `self._model.embed([query])`, which embeds the query as though it were a
  passage. BGE-v1.5 models are trained asymmetrically: queries get a special instruction prefix.
  fastembed exposes `TextEmbedding.query_embed()` for exactly this (confirmed present in your
  installed 0.8.0).
- Change: `embed_query` → `query_embed`.
- Acceptance: one-line change; eval re-run; delta recorded.

**2.2 — Embed the heading along with the chunk**
- File: `core/chunking/chunker.py:53`
- You extract the section heading, store it, display it — and then throw it away at embedding
  time. A chunk under "3.2 Scaled Dot-Product Attention" loses that context entirely.
- Change: embed `f"{heading}\n\n{text}"` while keeping `Chunk.text` clean for display.
  For personal admin documents, also prepend the filename stem — an invoice's only "heading"
  is often its name.
- Acceptance: eval re-run; delta recorded.

**2.3 — Switch the vector index from IVFFlat to HNSW**
- File: `core/index/pgvector.py:63`
- The IVFFlat index is created during `setup()` on an empty table. IVFFlat learns its cluster
  centroids from existing rows; built empty, it stays degenerate until manually rebuilt, quietly
  costing recall. HNSW has no training step and generally gives better recall for this scale.
  `docs/ARCHITECTURE.md` already (incorrectly) claims you use HNSW.
- Change: `USING hnsw (embedding vector_cosine_ops)`. Provide a migration note — this requires
  dropping the old index.
- Acceptance: eval re-run; index type matches the documentation.

**2.4 — Stop discarding tables**
- File: `core/ingest/extractor.py:7`
- `CONTENT_TYPES` excludes `"table"`. On `attention_2017.pdf`: **zero table blocks retained.**
  Annual reports are one third of your corpus and their tables *are* the content — this
  structurally guarantees that family underperforms.
- Change: include `"table"`; serialize table blocks to markdown-ish rows so they embed sensibly;
  add golden queries that target table content ("Berkshire's 2023 operating earnings").
- Acceptance: table blocks present in extraction output; financial-family recall improves.

**2.5 — Chunk-size guards**
- File: `core/chunking/chunker.py:36`
- Two unguarded ends. A single oversized block is never split (verified: a 3900-estimated-token
  block emits as one chunk) and bge-small silently truncates past 512 tokens. At the other end,
  heading flushes ignore `MIN_TOKENS`, producing chunks as small as **2 tokens** on real corpus
  documents.
- Change: hard-split blocks exceeding `MAX_TOKENS` at sentence boundaries; merge sub-`MIN_TOKENS`
  chunks into their neighbour. Consider ~15% overlap between adjacent chunks — standard practice
  that helps when an answer straddles a boundary.
- Acceptance: no chunk outside `[MIN_TOKENS, MAX_TOKENS]` across the whole eval corpus.

**2.6 — Implement D8 backfill**
- Files: `core/index/base.py`, `core/index/pgvector.py`, `core/api/routes/search.py`
- Change: when the date-filtered result count `< top_k`, run an unfiltered search and append the
  remainder. Add `within_date_range: bool` to `SearchResult` and the API response.
- Acceptance: a query whose date range matches 2 documents returns `top_k` results, with the
  first 2 flagged in-range.

---

### Phase 3 — Ingest cost: measure it, stop chasing it

**Status: performance investigation CLOSED. Do not reopen without a reason grounded in user
complaints, not benchmarks.**

Measured on this dev machine (12 cores, 15.7 GB). Per-file extraction cost scales with page
count and dominates everything else:

| Stage | attention_2017 (15pp) | 4-paper average (15–75pp) |
|---|---|---|
| Extraction (pymupdf4llm ONNX layout) | 16.6s | **44.2s** |
| Chunking | ~0.00s | ~0.00s |
| Embedding | 4.9s (31 chunks) | — |

**Four optimization hypotheses were tested. All four failed:**

| Hypothesis | Result |
|---|---|
| Disable the ONNX layout pass | **Impossible** — `to_json` and the `boxclass` API exist only in layout mode (`NotImplementedError`) |
| `pymupdf4llm.convert_batch(workers>1)` | **Broken here** — `FileNotFoundError` on every file, for absolute paths and both backends. `workers=1` works |
| `ProcessPoolExecutor` over `to_json` | **0.68x — a 47% slowdown** (259.5s vs 176.9s for 4 files). Output byte-identical, so correctness is fine; throughput is not |
| Extraction is internally multi-threaded, so cap threads | **No** — `OMP_NUM_THREADS=1` changed runtime by 8% (16.2s → 17.6s) |

A fifth check found **no per-process warm-up cost to amortize** — repeat `to_json` calls in one
process take the same time (17.0s / 20.6s / 18.9s), which also shows roughly ±20% run-to-run
noise on this machine.

Why the pool regresses is still unexplained; memory pressure across concurrent large documents
is the leading suspect (the library's own `auto_workers` budgets ~1 GB per worker). **It is not
worth resolving.** Tuning throughput against one developer laptop optimizes for a machine no
user will ever run.

**3.1 — Track ingest time as a regression metric instead**
- Files: `core/api/jobs.py` (already records `processing_ms` per file), new `reports/ingest.json`
- The pipeline already measures per-file processing time. Persist it: for each document, record
  `filename`, `page_count`, `bytes`, `processing_ms`, and the git commit.
- Report **ms per page**, not ms per file — raw file time is meaningless across a 15-page paper
  and a 75-page report, which is what made the early estimates in this plan misleading.
- Keep a best-ever figure per page-count bucket. If a change makes ingest slower, that shows up
  as a number rather than as a vague feeling that uploads got worse.
- Acceptance: after a bulk upload, `reports/ingest.json` holds one row per document, and a
  summary prints median and best ms/page.
- This is also a legitimate engineering artifact to talk about: *"instrumented the ingest path
  and tracked ms/page across commits"* is a stronger claim than a one-off optimization, and it
  is honest.

**3.2 — Never process the same PDF twice** *(the only unambiguous win — do this one)*
- Files: `core/index/pgvector.py`, `core/api/routes/upload.py`
- Re-uploading a file today creates a fresh `doc_id` and a duplicate corpus entry, paying the
  full extraction cost again.
- Change: SHA-256 the bytes, store on the `documents` table with a unique constraint on
  `(user_id, content_hash)`, and short-circuit to the existing document on collision.
- This removes work rather than rearranging it, which is why it survives when the parallelism
  ideas did not.
- Acceptance: uploading the same PDF twice yields one document and returns near-instantly the
  second time.

**3.3 — Make the wait visible rather than short**
- Upload is already asynchronous with per-file status. 45s/file matters far less when the user
  is not blocked and can watch progress.
- Change: surface per-file stage ("extracting" → "embedding" → "done") instead of a single
  `pending`, and show an estimate derived from page count using the 3.1 data.
- Acceptance: the dashboard shows which file is at which stage, never a frozen bar.

**3.4 — Bound the memory**
- File: `core/api/routes/upload.py`
- Every uploaded file is held fully in memory for the whole batch. There is a 50 MB per-file cap
  but no cap on file count — 20 files is ~1 GB resident.
- Change: cap file count per request (suggest 20); stream to a temp file instead of buffering.
- Acceptance: a 20-file batch does not spike RSS proportionally.


### Phase 4 — The features that make it a product (~3–5 days)

**4.1 — `documents` table**
- Prerequisite for most of what follows. `filename`, `user_id`, and `document_date` are
  currently repeated on every chunk row, so re-dating a document rewrites all of its chunks.
- Change: `documents(document_id PK, user_id, filename, document_date, content_hash, page_count,
  storage_path, created_at)`; `chunks.document_id` becomes a foreign key. Write a migration.
- Acceptance: `update_document_date` touches exactly one row.

**4.2 — Answer generation with citations**
- New: `core/answer/`
- Change: take the top-k chunks, prompt Claude with them, require inline citations that resolve
  to `chunk_id`. Stream the response. Refuse to answer when no chunk clears a relevance floor —
  "I couldn't find this in your documents" is a correct answer and builds far more trust than
  a confident fabrication.
- Note: this is your first external API dependency and breaks the local-first posture of D3/D4.
  Write it up as an ADR (D10) with the trade-off stated, and keep search working without it.
- Acceptance: every sentence with a factual claim carries a citation that resolves to a real chunk.

**4.3 — PDF highlighting**
- The `bbox` on every `SourceBlock` has been carried through the whole pipeline for exactly this.
- Change: on citation click, open the PDF at the chunk's page and draw highlight rectangles from
  the stored bboxes. Fix 0.5 first or every highlight lands one page off.
- Acceptance: clicking a citation opens the right page with the right region highlighted.

**4.4 — PDF bytes to object storage**
- Change: upload to Supabase Storage; store the path in `documents.storage_path`; serve via
  signed URLs rather than streaming through the API.
- Acceptance: PDFs survive a redeploy and serve correctly from a fresh container.

---

### Phase 5 — Before your friends touch it

**5.1 — Real authentication.** `user_id` is currently a query parameter, which means it is not
authentication at all: anyone can read, re-date, or wipe anyone's library by changing a string.
Supabase Auth issues JWTs; derive `user_id` from the verified token and never from user input.
Once that holds, enable Postgres RLS — which D2 already claims as the isolation mechanism but
which is not actually in play today, since the app connects with a single service-level
credential.

**5.2 — Rate limits and quotas.** Per-user caps on documents and total bytes.

**5.3 — Observability.** Structured logs for search latency, result counts, and zero-result
queries. Zero-result queries are your highest-value product feedback: they are a direct list of
what your users wanted and did not get.

---

## 4. Documentation debt (fold into the relevant phase)

- `README.md` says the evaluation framework is "Planned" (it is built) and reports 65 tests
  (91 pass). Endpoint table omits `/documents/{id}/pdf` and both `/eval/seed` routes.
- `ARCHITECTURE.md` claims HNSW (Phase 2.3 makes it true) and documents `ExtractedPage.page_number`
  as 0-indexed (Phase 0.5 makes it true).
- The documented error contract — `ValueError` for bad input, `RuntimeError` for infrastructure —
  is asserted in two documents and implemented in exactly one place. Either implement it in
  `extract()` and the API layer, or delete the claim.
- **"Hybrid search" is a misnomer.** In information retrieval, "hybrid" means dense + sparse
  (vector + BM25). Yours is semantic + metadata filter. Since Phase 1.4 adds a real BM25
  baseline, the term will collide with itself. Rename to "filtered semantic search" now, and
  reserve "hybrid" for if you later fuse BM25 and vector scores.

---

## 5. Suggested execution split

| Phase | Recommended | Why |
|---|---|---|
| 0 | Sonnet | Well-specified, mechanical, each task has a test |
| 1.1–1.3, 1.6 | Sonnet | Precise, localized fixes with clear acceptance |
| 1.4–1.5, 1.7 | Opus / together | Baseline design and golden-set authoring are judgment calls |
| 2 | Opus / together | Requires reading eval deltas and deciding what to keep |
| 3 | Sonnet | Mechanical. Perf investigation is closed — do 3.1/3.2, do not re-benchmark |
| 4 | Together | Product design decisions throughout |
| 5 | Together | Security-critical |

Rule of thumb: hand Sonnet anything with a **binary acceptance test**. Keep anything where the
next step depends on interpreting a number.

---

## Appendix — the jargon, briefly

- **BM25** — the classic keyword ranking algorithm (a smarter TF-IDF). It rewards rare query
  words appearing often in a short document. It is the standard "did semantic search actually
  help?" baseline, and it genuinely beats embeddings on exact-term queries like invoice numbers.
- **IVFFlat / HNSW** — two ways Postgres can index vectors so it does not compare your query to
  every row. IVFFlat clusters vectors and searches the nearest clusters; it must *learn* those
  clusters from real data, so building it on an empty table leaves it degenerate. HNSW builds a
  navigable graph incrementally, needs no training pass, and generally recalls better at this
  scale. That is why Phase 2.3 switches.
- **bge query prefix** — `bge-small-en-v1.5` was trained with queries and passages phrased
  differently: queries carry a short instruction prefix. Embedding a query without it puts it in
  slightly the wrong place in vector space. `query_embed()` adds it. Cheapest quality win here.
- **nDCG / IDCG** — nDCG scores whether *good results are ranked near the top*, discounting hits
  further down. IDCG is the score of the perfect ranking, used to normalize into `[0, 1]`. The
  current bug computes IDCG from what was retrieved rather than from what *should* have been
  retrieved, so any well-ordered-but-mediocre result set scores a perfect 1.0.
- **Precision vs. Recall** — precision asks "of what I returned, how much was right?"; recall
  asks "of everything right, how much did I return?". For your product **recall matters more**:
  a user who cannot find their document at all is far more upset than one who scrolls past two
  bad results.
