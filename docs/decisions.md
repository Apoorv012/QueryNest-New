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
