# Learning Notes — QueryNest

What to understand about this project, and how to talk about it. Written for interview prep:
every claim here is backed by something that actually happened in this repo, with numbers.

---

## 0. The one-line framing

> QueryNest is semantic search over personal PDFs. Users search by meaning instead of filename,
> optionally scoped by a natural-language date expression, and get answers with citations.

If someone asks what was hard: **it was not the machine learning.** Six things broke during
development. One was ML-adjacent. The rest were database indexing, networking, SQL semantics,
process management, and experiment design. That answer is more honest and more interesting than
"tuning embeddings", and it is what the commit history shows.

---

## 1. Retrieval metrics — the minimum that is actually enough

| Metric | Question it answers | When it matters here |
|---|---|---|
| **Precision@K** | Of what I returned, how much was right? | Weak signal for this product — see the ceiling trap below |
| **Recall@K** | Of everything right, how much did I return? | **The one that matters.** A user who cannot find their file at all is far angrier than one who scrolls past two bad results |
| **MRR** | How far down was the *first* right answer? | Strong proxy for "find me the file" — users look at the top result |
| **nDCG@K** | Are the *most* relevant results near the top? | Handles graded relevance (2 = directly answers, 1 = related) and discounts lower positions |

### The three traps (all of which bit this project)

**1. Every metric has a ceiling set by your dataset, not your system.**
Precision@K divides by K regardless of how many relevant documents exist. This corpus averages
**1.40 relevant documents per query**, so a query with one relevant document scores at most 0.20
at K=5. The maximum achievable Precision@5 here is **0.2800**. Measured: 0.2578 — which is *92%
of the ceiling*, not the "26%" it looks like.

> *Interview answer:* "Precision@5 was 0.26, which sounds terrible until you notice the ceiling
> is 0.28 — with 1.4 relevant docs per query you mathematically cannot score higher. I report
> Recall@5 and MRR instead, and quote precision against its ceiling."

**2. Metrics can be implemented wrong and still look plausible.**
Two real bugs found here:
- `recall_at_k` divided duplicate-containing hits by a *set* size, so it returned **5.0**.
- `nDCG` computed the ideal ranking from *what was retrieved* instead of the ground truth, so
  any well-ordered result set scored exactly **1.0** — including one where every hit was merely
  "somewhat relevant".

**3. Document-level vs chunk-level must be a deliberate choice.**
Relevance here is judged per *document*, but retrieval returns *chunks*, and one document can
supply many chunks. Without de-duplicating to document level first, duplicates inflate recall
past 1.0. Chunk-level evaluation was rejected because it requires labelling chunk ids, which
churn every time chunking parameters change.

**Read:** Manning, Raghavan & Schütze, *Introduction to Information Retrieval*, **Chapter 8**
only (free at `nlp.stanford.edu/IR-book`). ~20 pages, canonical.

---

## 2. Evaluation as experiment design — the real skill

Metrics are an afternoon. **Knowing why your number is lying to you** is the skill, and it is
what this project actually exercised.

### The habits, in order of value

1. **A number without a baseline means nothing.** Recall@5 of 0.94 sounds excellent — until a
   keyword baseline also scores 0.88.
2. **A baseline you built can be built wrong, in either direction.** Both of ours were:
   - *Filename search* — its score is set by how you happened to name fixture files. Name them
     `attention_2017.pdf` and it wins; name them `x.pdf` and it scores zero. Any "N× better"
     figure would be **authored, not measured**. Rejected outright.
   - *Keyword search v1* — used `websearch_to_tsquery`, which **ANDs** every term, so a chunk had
     to contain every word of a natural-language question. It returned **zero documents for 24 of
     45 queries**. It scored 0.39 not because keyword search is weak but because it never ran.
3. **Change one thing, measure, write it down — including failures.**
4. **Negative results are results.** Documented here so they are not retried: the BGE query
   prefix (a regression), and four separate ingest-parallelism hypotheses (all failed).
5. **Suspect your measurement before your system.** Identical numbers to four decimal places
   meant a stale server, not "no effect".

### Ceilings, floors, and confounds

A confound is anything that moves your number for a reason unrelated to what you are testing.
Real ones from this project: an untrained index, a stale process, AND-semantics in the baseline,
and query vocabulary bias. **Four of six "findings" were initially confounds.**

---

## 3. The query-vocabulary trap — the most interesting result here

The first keyword baseline, once fixed, produced an uncomfortable result:

| Metric | Semantic | Keyword |
|---|---|---|
| Recall@5 | 0.9444 | 0.8833 |
| **MRR** | 0.9000 | **0.9025** |

**Semantic search was not beating keyword search.** Keyword even won MRR.

The cause: the golden queries had been written *by reading the documents*, so they reused the
documents' own vocabulary. Mean lexical overlap with the target document was **0.798**. Keyword
search wins those trivially — and that is not the case the product exists to serve.

So a second query set was written, deliberately phrased the way someone half-remembers a
document (overlap **0.565**):

> *"the paper that let every word look at every other word instead of reading in order"*
> rather than *"the attention mechanism in transformers"*

| | Literal (45q) | Paraphrased (40q) |
|---|---|---|
| Semantic MRR | 0.9000 | 0.7896 |
| Keyword MRR | 0.9025 | 0.6656 |
| Delta | −0.003 (**tie**) | **+0.124 semantic** |

**Keyword retrieval degrades 26% when the user stops using the document's words; semantic
degrades 12% — less than half.**

> *Interview answer:* "My first comparison showed semantic search barely beating keyword search.
> Rather than ship that number, I worked out why: I'd written the queries while reading the
> documents, so I'd used their vocabulary — the exact case keyword search wins. I wrote a second
> query set that avoided document vocabulary and measured the overlap to prove it did. Semantic
> ties on literal queries and leads 19% on paraphrased ones. That's a better claim than the one
> I set out to make, because it says *when* each approach helps."

This is the strongest story in the project: **it made your own system look worse and you
reported it anyway.**

---

## 4. Latency — p50, p95, and why the mean lies

- **The mean hides tails.** One 2-second request among ninety-nine 10 ms ones gives a mean of
  30 ms, describing nobody's actual experience.
- **p50** = the typical user. **p95/p99** = your unluckiest users — the ones who complain and churn.
- **Separate cold start from steady state.** First query here is 35.9 ms vs 16.2 ms warm; the
  difference is ONNX model loading, not search.

**Current numbers:** search **p50 16.2 ms**, p95 19.5 ms. Breakdown: date parsing 0.04 ms, query
embedding ~5 ms, pgvector HNSW lookup ~8 ms, HTTP ~3 ms.

### The measurement trap that made all of this wrong for a while

Every reported latency was **~2,080 ms** until the cause was found: the eval hit
`http://localhost:8000`. On Windows `localhost` resolves to IPv6 `::1` first, uvicorn binds
IPv4-only, so every request stalled ~2 s on a failed IPv6 attempt before falling back.

**2083 ms via `localhost` vs 16 ms via `127.0.0.1` for an identical request — 130×.**

> *Interview answer:* "I was about to report 2-second search latency. The number was suspiciously
> uniform — 2030 to 2103 ms — which suggested a fixed cost rather than real work. Profiling
> in-process showed the actual search was 13 ms, so the 2 seconds were in the HTTP path. It was
> IPv6 fallback on Windows."

**Read:** Dean & Barroso, *"The Tail at Scale"* (CACM, 2013). Short, famous, permanently changes
how you read latency numbers.

**Ingest:** ~**1,790 ms/page** (extraction 77%, embedding 23%, chunking ~0). Always track per
*page*, never per file — this corpus spans 2–43 page documents, so per-file numbers vary 4× for
reasons unrelated to code.

---

## 5. Vector search — what actually matters

### The bug worth understanding deeply

`setup()` created the index as `USING ivfflat (...) WITH (lists = 100)`. `setup()` runs at
startup — **against an empty table**.

IVFFlat clusters vectors and searches only the nearest clusters. It learns those cluster centres
**from the rows present when the index is built**. With no rows, the 100 lists were never
trained. pgvector's default `ivfflat.probes = 1` then scans exactly one degenerate list per
query and frequently finds nothing.

| Query path | Rows returned |
|---|---|
| Default (`probes = 1`) | **0** |
| `SET ivfflat.probes = 100` | 10 |
| Index disabled (exact scan) | 10 |

Fix: **HNSW**, which builds a navigable graph incrementally as rows are inserted and so has no
training step to miss.

| Metric | Untrained IVFFlat | HNSW |
|---|---|---|
| Recall@5 | 0.5944 | **0.9444** |
| MRR | 0.5852 | **0.9000** |
| nDCG@10 | 0.5495 | **0.8993** |

> *Interview answer:* "Search was silently returning zero results for about half of queries. I
> caught it because an eval scored suspiciously low and two queries returned nothing at all —
> not bad ranking, no rows. The vector index was IVFFlat, which learns cluster centroids from
> existing data, but it was created at startup against an empty table, so it was never trained.
> With the default probe setting a query scanned one degenerate cluster and found nothing.
> Switching to HNSW took Recall@5 from 0.59 to 0.94."

**IVFFlat vs HNSW, the short version:** IVFFlat is cheaper to build and smaller, but must be
built *after* data exists and needs `probes` tuning. HNSW builds incrementally, generally recalls
better, costs more memory and build time. At personal-library scale, HNSW is the safe default.

**Read:** the pgvector README's indexing section. About an hour, highest ROI available.

---

## 6. Chunking and embeddings — practitioner level

You are a *user* of the embedding model, not a trainer. What matters:

- **Chunk boundaries decide what can be retrieved.** This project chunks on heading boundaries
  (`section-header` blocks from the PDF layout model), flushing on heading change or token
  overflow.
- **Token limits truncate silently.** `bge-small-en-v1.5` caps at 512 tokens. A chunk over that
  loses its tail with no error. `MAX_TOKENS = 400` with a `words × 1.3` estimate is a safety
  margin, not a guarantee.
- **Overlap exists because answers straddle boundaries.** Not yet implemented here.
- **Asymmetric models.** BGE-v1.5 is trained with a query-side instruction prefix. Applying it
  here was a **regression** (Recall@5 0.9444 → 0.8944) — plausibly because these queries are
  already long and descriptive, so the prefix mostly added noise. Also worth knowing:
  fastembed's `query_embed()` is a **no-op** for this model, returning vectors identical to
  `embed()` (cosine 1.0).

**Skip for now:** transformer internals, training, fine-tuning. Interesting, not on the critical
path for building this.

---

## 7. Designing for what the system actually knows

A recurring theme worth being able to articulate.

Date filtering went through three designs:

1. **Hard filter.** `document_date >= x`. Broke immediately: SQL `NULL >= x` is *false*, so every
   undated document vanished from any date-filtered search — and **7 of 17 documents have no
   detectable date**.
2. **Widened predicate + backfill.** `(document_date IS NULL OR document_date >= x)`, topping up
   short result sets from an unfiltered search. Fixed the disappearance, but reported undated
   documents as `within_date_range: true` — asserting a match that was never verified.
3. **Three tiers** (current): `in_range` → `undated` → `out_of_range`, served in that order.

The insight in step 3: **"unknown" and "known wrong" are different, and a boolean cannot express
the difference.** An undated document might be the one you want. A document dated 2019 when you
asked for 2023 is a verified non-match. So unknown ranks above known-wrong — and tier order
deliberately beats similarity score.

> *Interview answer:* "The data model was claiming certainty the system didn't have. A boolean
> forced undated documents to be labelled either in-range or out-of-range, and both are lies —
> we simply don't know. Three states let the ranking encode confidence instead."

---

## 8. Systems debugging — where the time actually goes

Unglamorous and highest-frequency. Every one of these cost real time here:

| Symptom | Cause |
|---|---|
| Correct password rejected by Postgres | A **native** Postgres service owned port 5432 and answered ahead of the Docker container. Moved the container to 5433 |
| Code changes having "no effect" | `pkill -f uvicorn` does not work on Windows. Old server survived, new one failed to bind (exit 3), eval ran against **stale code** — twice |
| 2-second latency | IPv6 `localhost` resolution (§4) |
| `local` mode writing to production | `LocalPgVectorStore` fell back to `QUERYNEST_DATABASE_URL` when its own variable was unset, so `STORAGE_MODE=local` silently connected to Supabase |
| 35 junk rows in production | The **test suite** was indexing fixture PDFs into the real database, because `_has_pgvector` was computed at import time from `.env` |

The last two share a lesson: **make wrong configurations impossible rather than unlikely.** Two
separate connection-string variables cannot alias onto one database; one variable with a fallback
can.

---

## 9. Security — what an interviewer will probe

- **Path traversal.** `GET /documents/{id}/pdf?user_id=..` served any PDF on disk. `user_id` was
  an unvalidated string used to build a filesystem path. Fixed with a charset allowlist *and* a
  resolved-path containment check — defence in depth, because either alone can be bypassed.
- **Silent failure is worse than loud failure.** Uploads caught `(RuntimeError, OSError)` around
  indexing and reported `"done"` regardless. Files appeared uploaded but were unsearchable. Worse,
  `psycopg2.Error` is neither of those, so a DB error escaped and pinned the job at `"pending"`
  forever.
- **Auth is still open.** `user_id` is a query parameter, so anyone can read anyone's library.
  Known, documented, not yet fixed — say so plainly rather than pretending otherwise.

---

## 10. Prioritised reading

1. **pgvector README, indexing section** — ~1 hour, highest ROI.
2. **IIR Chapter 8** — evaluation metrics, ~20 pages.
3. **Postgres full-text search docs** — `tsvector`, `tsquery`, `ts_rank`, and how the query
   builders differ (`websearch_to_tsquery` ANDs; that detail cost a whole broken baseline).
4. **Dean & Barroso, "The Tail at Scale"** — latency percentiles.
5. **RAG fundamentals** — chunking, overlap, hybrid search. Practitioner depth only.

---

## 11. The three stories to be able to tell precisely

Rehearse these. Each is: *what I saw → what I suspected → how I confirmed it → what it cost.*

1. **"My search was silently returning zero results."** Untrained IVFFlat on an empty table.
   Found via a suspiciously low eval score and two queries returning nothing. Recall@5 0.59 → 0.94.
2. **"My baseline was broken and made my system look 3× better than it was."** Fixed it, the
   advantage mostly vanished, so I isolated *where* semantic search genuinely helps instead.
3. **"I nearly reported 2-second search latency."** Suspicious uniformity → profiled in-process →
   13 ms real → IPv6 resolution in the HTTP path.

Story 2 is the strongest. Most candidates have never reported a result that undercut their own
work, and it is exactly the instinct senior engineers are hired for.
