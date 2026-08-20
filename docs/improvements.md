# Improvements Log

Track notable optimizations, refactors, and technical decisions with measurable outcomes.

---

## Test Suite: 86% Reduction in Test Runtime

**Problem:** 12 tests taking ~240s (4 minutes). Each test independently called `pymupdf4llm.to_json()` on a 15-page PDF, running full layout analysis multiple times per test file.

**Root cause:** No shared state between tests. Each invocation of `extract()` triggered pymupdf4llm's C-engine layout analysis pipeline (multi-column detection, heading classification, reading-order reconstruction) from scratch.

**Fix:** Module-level cached extraction. A single `extract()` call per test file, with results shared across all tests via a module-scope cache variable.

```python
_doc = None

def _get_doc():
    global _doc
    if _doc is None:
        _doc = extract(SAMPLE_PDF)
    return _doc
```

**Outcome:** Test suite runtime reduced from **240s to 35s** — an **86% reduction**.

---

## Ingestion Pipeline: Replaced Custom Extraction with Layout-Aware Library

**Problem:** The original ingestion pipeline used 4 custom modules (~250 lines) to process raw PyMuPDF output into searchable text:

- `extractor.py` (32 lines) — manual page→block→line→span traversal
- `normalizer.py` (109 lines) — span-to-line merging (Y-axis tolerance), line-to-paragraph merging (gap threshold)
- `cleanup.py` (76 lines) — regex header/footer detection, page number removal, non-language filtering
- `heading.py` (32 lines) — regex heuristics for heading detection (numbered, roman numerals, ALL-CAPS)

Each module had tunable constants (e.g., `LINE_Y_TOLERANCE = 2.5pt`, `PARA_GAP = 10.0pt`, `MIN_PAGE_REPEATS = 3`) with no way to measure whether they improved retrieval quality.

**Fix:** Replaced with `pymupdf4llm.to_json()` — a single library call that provides layout-aware extraction:
- Multi-column reading-order reconstruction
- Paragraph-level grouping (each layout box = one logical paragraph)
- Heading detection via font-size hierarchy
- Header/footer separation via layout classification
- Table, image, and formula detection

New extraction: ~40 lines. Removed 3 modules entirely.

**Outcome:**
- ~210 lines of custom heuristic code removed
- Extraction quality improved (layout-aware vs. position-based heuristics)
- Pipeline reduced from 5 stages to 2 (extract → chunk)

---

## Vector Index: Untrained IVFFlat Was Returning Zero Results

**Date:** 2026-08-20

**Problem:** Search silently returned empty result sets for a large fraction of queries. It
surfaced only when the first golden-set evaluation scored `Recall@5 = 0.5944` and two queries
returned literally nothing — not bad ranking, no rows at all.

**Root cause:** `PgVectorStore.setup()` created the vector index as

```sql
CREATE INDEX idx_chunks_embedding ON chunks
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
```

`setup()` runs at application startup, i.e. **against an empty table**. IVFFlat learns its
cluster centroids from the rows present when the index is built, so with no rows the 100 lists
were never trained. pgvector's default `ivfflat.probes = 1` then scans exactly one of those
degenerate lists per query, and frequently finds nothing in it.

Measured on the seeded corpus (586 chunks, 17 documents):

| Query path | Rows returned |
|---|---|
| Default (`ivfflat.probes = 1`) | **0** |
| `SET ivfflat.probes = 100` | 10 |
| Index disabled (exact scan) | 10 |

**Fix:** Switched to HNSW, which builds its graph incrementally as rows are inserted and
therefore has no training step to miss. `setup()` now drops the old IVFFlat index and creates
`idx_chunks_embedding_hnsw`.

**Outcome** — across 45 golden queries, same corpus, same embeddings, index type the only change:

| Metric | Untrained IVFFlat | HNSW | Change |
|---|---|---|---|
| Recall@5 | 0.5944 | **0.9444** | +59% |
| MRR | 0.5852 | **0.9000** | +54% |
| nDCG@10 | 0.5495 | **0.8993** | +64% |
| Precision@5 | 0.1556 | 0.2578 | +66% |

**Note:** the same defective index exists on any database where `setup()` ran before this fix,
including hosted Supabase. Running `setup()` once against each environment rebuilds it.

---

## Eval Corpus: 45-Page Cap Cut Re-Seed Time by 85%

**Date:** 2026-08-20

**Problem:** A full corpus re-seed took ~23 minutes, which made Phase 2's "change one thing,
re-run the eval" discipline unaffordable in practice — four retrieval changes would have cost
an hour each, and the discipline would have been abandoned.

**Root cause:** Four full annual reports (`gsk_2024` 344pp, `unilever_2024` 305pp, `ppl_2024`
170pp, `berkshire_2024` 150pp) accounted for 1,087 of 1,228 corpus pages — **88% of extraction
cost for 4 of 14 documents**. Extraction is ~1.1s/page and dominates ingest (77% of per-file
cost; chunking is ~0s and embedding ~23%).

**Fix:** Capped corpus documents at ~45 pages (decision D10). Excluded the four large reports
plus `gpt3_2020` (75pp). Rationale is product-led as well as economic: QueryNest targets
general public use, and a 344-page annual report is not a document its users own.

**Outcome:**
- Re-seed time **23 min → 3.5 min** (measured 7.4 min for the final 17-document corpus, which
  also added 8 new short documents).
- Per-change attribution during retrieval tuning became affordable, which is what made the
  IVFFlat finding above measurable at all.
- Cost: 9 of 30 golden queries became unanswerable and were retired; the golden set was rebuilt
  to 45 queries covering all 17 documents.
