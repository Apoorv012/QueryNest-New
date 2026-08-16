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
