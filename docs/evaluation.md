# Evaluation Framework

This document describes the evaluation methodology for QueryNest's search quality. The goal is to measure retrieval accuracy with concrete metrics and reproducible test data.

---

## Overview

QueryNest is a semantic search engine for PDFs. Evaluation focuses on **retrieval quality** — given a query, does the system return the right chunks from the right documents?

Evaluation happens in three layers:
1. **Retrieval metrics** — Precision, Recall, NDCG (automated)
2. **End-to-end quality** — Answer correctness with LLM-as-judge (future)
3. **Human evaluation** — Subjective relevance judgments (future)

This document covers Layer 1 (retrieval metrics).

---

## Metrics

### Precision@K

**Definition**: Of the top-K results returned, how many are actually relevant?

```
Precision@K = (relevant results in top-K) / K
```

**Example**: If you search for "deadlock prevention" and get 5 results, 4 of which are about deadlock prevention, Precision@5 = 0.8.

**Target**: > 0.7 (70% of results should be relevant)

### Recall@K

**Definition**: Of all relevant documents in the corpus, how many did we retrieve in top-K?

```
Recall@K = (relevant results in top-K) / (total relevant in corpus)
```

**Example**: If there are 10 chunks about "deadlock prevention" in your PDFs, and you retrieve 7 of them in top-10, Recall@10 = 0.7.

**Target**: > 0.8 (80% of relevant docs should be found)

### NDCG@K (Normalized Discounted Cumulative Gain)

**Definition**: Are relevant results ranked higher than less relevant ones?

NDCG rewards placing highly relevant results at the top. A result at position 1 counts more than position 5.

**Formula**:
```
DCG@K = Σ (2^relevance_i - 1) / log2(i + 1)
NDCG@K = DCG@K / IDCG@K  (ideal DCG)
```

**Relevance scale**: 0 (irrelevant), 1 (somewhat relevant), 2 (highly relevant)

**Target**: > 0.75

### MRR (Mean Reciprocal Rank)

**Definition**: What is the rank of the first relevant result?

```
MRR = 1 / rank_of_first_relevant
```

**Example**: If the first relevant result is at position 2, RR = 0.5. Average across all queries.

**Target**: > 0.8 (first relevant result should be in top 1-2)

---

## Test Data

### Categories

| Category | Source | Purpose |
|---|---|---|
| **Question Papers** | University exams | Test factual retrieval (definitions, formulas) |
| **Academic Papers** | arXiv, IEEE, ACM | Test conceptual retrieval (methods, results) |
| **Accounting Papers** | Annual reports, audits | Test numerical/metadata retrieval |

### Sample PDFs Needed

**Question Papers (5-10 PDFs)**:
- Computer Science exams (OS, DBMS, Networks, Algorithms)
- Math exams (Calculus, Linear Algebra, Probability)
- Physics exams (Mechanics, Electromagnetism)

**Academic Papers (10-15 PDFs)**:
- AI/ML papers (transformers, embeddings, RAG)
- Systems papers (databases, distributed systems)
- Theory papers (complexity, algorithms)

**Accounting Papers (5-10 PDFs)**:
- Annual reports (public companies)
- Financial statements
- Audit reports

### Query Types

| Type | Example | Tests |
|---|---|---|
| **Factual** | "What is the time complexity of quicksort?" | Direct fact retrieval |
| **Definitional** | "Define virtual memory" | Concept matching |
| **Comparative** | "Compare TCP and UDP" | Multi-chunk retrieval |
| **Procedural** | "How does garbage collection work?" | Sequential understanding |
| **Lookup** | "Find papers about BERT" | Keyword + semantic matching |

---

## Golden Dataset

### Structure

```json
{
    "queries": [
        {
            "id": "q1",
            "query": "What is the time complexity of quicksort?",
            "type": "factual",
            "expected_docs": [
                {
                    "document_filename": "algorithms_paper.pdf",
                    "relevance": 2,
                    "text_contains": "O(n log n)"
                }
            ],
            "min_relevant": 1
        }
    ]
}
```

Parsed by `core.eval.runner.load_golden()`. Relevance is judged per **document**, matched against `document_filename` (the original filename's stem, e.g. `attention_2017`). Search results only carry the store-assigned `document_id` (a random hex id, unrelated to the filename), so `run_eval()` resolves `document_id -> filename` via `GET /documents` (`get_document_filename_map()`) before comparing against the golden set. `text_contains` is currently informational only and isn't checked by the runner.

### Relevance Scale

| Score | Meaning | Example |
|---|---|---|
| **2** | Highly relevant | Directly answers the question |
| **1** | Somewhat relevant | Related but doesn't directly answer |
| **0** | Irrelevant | Wrong topic or wrong document |

### Dataset Size

- **Minimum**: 50 queries across all categories
- **Target**: 100+ queries
- **Distribution**: 40% factual, 30% definitional, 20% comparative, 10% procedural

---

## Evaluation Process

### Step 1: Index Test PDFs

```bash
# Download fixture PDFs (academic + accounting) into data/eval/pdfs/<category>/
python -m core.eval.download_pdfs

# With the API running (uvicorn core.api.main:app), re-index them for the
# dedicated golden_user, replacing anything previously seeded:
curl -X POST http://localhost:8000/eval/seed
curl http://localhost:8000/eval/seed/{job_id}/status   # poll until done
```

`POST /eval/seed` (`core/api/routes/eval.py`) walks `data/eval/pdfs/`, extracts, chunks, date-detects, embeds, and stores each PDF under a fixed `golden_user`, tracked as a background job via `core/api/jobs.py`. Note: none of the API routes are mounted under an `/api` prefix — `main.py` includes `api_router` with no prefix, so every route (`/search`, `/documents`, `/upload/bulk`, `/eval/seed`, ...) hangs directly off the app root.

### Step 2: Run Evaluation

```bash
# Run evaluation against data/eval/golden.json (requires the API running)
python -m core.eval
```

### Step 3: Generate Report

Output (`core/eval/report.py: print_report`, printed to console) plus a JSON file written to `reports/report_<timestamp>_<git_commit>.json` (`generate_report`), containing aggregate metrics, latency, a by-type breakdown, the 5 worst queries by MRR, and full per-query results:

```
QueryNest Evaluation Report (100 queries)
==================================================
  Precision@5:  0.7800
  Precision@10: 0.7200
  Recall@5:     0.6500
  Recall@10:    0.8500
  NDCG@10:      0.8200
  MRR:          0.9100

By Query Type:
  factual         P@5=0.82  R@10=0.88  (n=40)
  definitional    P@5=0.75  R@10=0.83  (n=30)
  comparative     P@5=0.71  R@10=0.79  (n=20)
  procedural      P@5=0.80  R@10=0.87  (n=10)

Worst Queries:
  q42: "Compare consensus algorithms" (MRR=0.40, P@5=0.40)
  q67: "What is vector quantization?" (MRR=0.50, P@5=0.50)
```

### Step 4: Analyze Failures

For each low-scoring query:
1. What did the system return?
2. What should it have returned?
3. Why did it fail? (chunking, embedding, ranking)

---

## Baseline Benchmarks

### Target Performance

| Metric | Minimum | Good | Excellent |
|---|---|---|---|
| Precision@5 | 0.60 | 0.75 | 0.85 |
| Recall@10 | 0.70 | 0.80 | 0.90 |
| NDCG@10 | 0.65 | 0.75 | 0.85 |
| MRR | 0.75 | 0.85 | 0.95 |

### Comparison Points

- **BM25 (keyword search)**: Baseline for traditional search
- **OpenAI embeddings**: Commercial baseline
- **BGE-large**: Stronger open-source model

---

## Evaluation Tools

### Required

- **pytest**: Test framework
- **numpy**: Metric calculations
- **json**: Golden dataset storage

### Optional (Future)

- **Ragas**: LLM-as-judge evaluation
- **BEIR**: Standard retrieval benchmark
- **DeepEval**: Production RAG monitoring

---

## Running Evaluation

```bash
# Unit-test the metric functions (precision/recall/ndcg/mrr)
pytest tests/eval/ -v

# Run the full evaluation against the golden set (API must be running) and
# print + save a report
python -m core.eval
```

---

## Iteration Process

1. **Baseline**: Measure current performance
2. **Identify failures**: Which queries fail and why?
3. **Hypothesize**: Is it chunking? Embedding? Ranking?
4. **Experiment**: Change one variable at a time
5. **Measure**: Re-run evaluation
6. **Compare**: Did performance improve?

Common improvements:
- Adjust chunk size (MAX_TOKENS, MIN_TOKENS)
- Try different embedding models
- Add metadata filters
- Improve query parsing

---

## Current Baseline (2026-08-20)

Committed reports live in `data/eval/baselines/` (the `reports/` directory is gitignored, so
canonical runs are copied there deliberately).

**Corpus:** 17 documents / 586 chunks, all ≤45 pages (D10), seeded under `golden_user`.

| Family | Docs |
|---|---|
| Academic | 8 |
| Financial | 2 |
| Career / study | 7 |

**Golden set:** 45 queries, covering all 17 documents.
factual 11 · definitional 10 · lookup 7 · temporal 7 · comparative 6 · procedural 4.
All 7 temporal queries verified to parse an actual date range through `parse_query`.

**Results** (`2026-08-20_hnsw_baseline.json`, commit `a2a056b`):

| Metric | Value |
|---|---|
| Recall@5 | **0.9444** |
| Recall@10 | 0.9444 |
| nDCG@10 | **0.8993** |
| MRR | **0.9000** |
| Precision@5 | 0.2578 |

### How to read these — three traps

**1. Precision is capped by the golden set, not by retrieval.** This corpus averages **1.40
relevant documents per query**, so a query with one relevant document scores at most 0.20 at
P@5 no matter how perfect the ranking. The theoretical maximum here is:

| | Ceiling | Achieved | % of ceiling |
|---|---|---|---|
| Precision@5 | 0.2800 | 0.2578 | **92%** |
| Precision@10 | 0.1400 | 0.1289 | 92% |

Raw precision on this corpus measures the shape of the golden set. **Do not quote it without
the ceiling**; quote Recall@5, MRR and nDCG@10 instead.

**2. Recall@5 and Recall@10 are identical** because retrieval is deduplicated to document level
(see below) and 10 chunks rarely span more than 5 distinct documents. `@10` carries no extra
information at this corpus size.

**3. Evaluation is document-level.** Relevance is judged per document, and `run_eval`
deduplicates retrieved documents (first occurrence wins, rank preserved) before computing any
metric. Chunk-level evaluation was rejected: it requires labelling chunk ids, which churn every
time chunking parameters change — exactly what Phase 2 does.

### Not yet suitable for external claims

There is **no baseline to compare against yet**. A metric without a baseline is not an
achievement, and filename search is explicitly *not* a valid baseline — its score is determined
by how the fixture files happen to be named, so any "N× better" figure would be authored rather
than measured. BM25 over document content is the comparison being built (Phase 1.4).

### Rejected changes (do not retry)

| Change | Result |
|---|---|
| BGE query-instruction prefix on `embed_query` | **Regression**: Recall@5 0.9444 → 0.8944. Report: `2026-08-20_rejected_bge-query-prefix.json` |
| `fastembed.query_embed()` instead of `embed()` | **No-op**: returns identical vectors (cosine 1.0) for `bge-small-en-v1.5` |

### Measurement procedure

Retrieval changes are measured one at a time, re-seeding between any change that alters what
gets indexed. Note that **query-side changes need no re-seed**, but **do require restarting the
API** — and on Windows `pkill -f uvicorn` does not kill it. The replacement silently fails to
bind port 8000 and the eval runs against stale code, producing identical numbers that look like
"no effect". Free the port explicitly first:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```
