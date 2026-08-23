
from core.models.chunk import Chunk
from core.models.extracted import ExtractedBlock, ExtractedDocument

from .tokenizer import estimate_tokens

MAX_TOKENS = 400
MIN_TOKENS = 120

# Chunks below this are dropped at ingest rather than indexed.
#
# A `section-header` flushes the current chunk and then becomes the first block
# of the next, so two consecutive headings emit a chunk whose entire content is
# the first heading — "4 Results", "E Additional Details", "APPENDIX". At 2-3
# tokens these embed to a vague near-centroid vector sitting at middling
# distance from *every* query, so they surface as plausible-looking noise
# (measured: ranks 3 and 6 for "job descriptions", from an AI paper and a RAG
# paper, ahead of three actual job descriptions).
#
# Dropped rather than merged: merging folded them *into* neighbours, changing
# the boundaries of good chunks too, and cost document-level recall. Dropping
# touches only the unusable chunk. Nothing is lost either — such a chunk's
# entire text is a heading, which is already stored separately as
# `Chunk.heading`.
#
# Dropped at ingest rather than filtered at query time: a chunk that can never
# be a useful result should not occupy an index slot, an HNSW graph node, and a
# check on every result forever.
DROP_BELOW_TOKENS = 20


def chunk_document(doc: ExtractedDocument) -> list[Chunk]:
    blocks = [
        b for page in doc.pages for b in page.blocks
    ]
    # Two separate concerns, deliberately kept apart: `_chunk_blocks` decides
    # where boundaries fall (headings, token overflow); `_drop_unusable` then
    # discards the results that are too small to ever be a useful search hit.
    # Keeping the boundary logic pure means it stays directly testable.
    return _drop_unusable(_chunk_blocks(blocks))


def _drop_unusable(chunks: list[Chunk]) -> list[Chunk]:
    """Discard chunks too small to be a useful search result (see DROP_BELOW_TOKENS).

    If *every* chunk is below the threshold the document is kept as-is: a
    genuinely tiny document (a one-line receipt, a scanned cover page) should
    still be findable, and returning nothing would silently drop it from the
    corpus entirely.
    """
    kept = [c for c in chunks if estimate_tokens(c.text) >= DROP_BELOW_TOKENS]
    if not kept:
        return chunks
    for i, chunk in enumerate(kept):
        chunk.chunk_index = i
    return kept


def _chunk_blocks(blocks: list[ExtractedBlock]) -> list[Chunk]:
    chunks: list[Chunk] = []
    current_blocks: list[ExtractedBlock] = []
    current_tokens = 0
    current_heading = ""
    chunk_index = 0

    for block in blocks:
        tokens = estimate_tokens(block.text)

        if block.type == "section-header":
            if current_blocks:
                chunks.append(_flush(current_blocks, current_heading, chunk_index))
                chunk_index += 1
                current_blocks = []
                current_tokens = 0
            current_heading = block.text.strip()

        elif current_tokens + tokens > MAX_TOKENS and current_tokens >= MIN_TOKENS:
            chunks.append(_flush(current_blocks, current_heading, chunk_index))
            chunk_index += 1
            current_blocks = []
            current_tokens = 0

        current_blocks.append(block)
        current_tokens += tokens

    if current_blocks:
        chunks.append(_flush(current_blocks, current_heading, chunk_index))

    return chunks


def _flush(blocks: list[ExtractedBlock], heading: str, chunk_index: int) -> Chunk:
    return Chunk(
        text="\n".join(b.text for b in blocks),
        source_blocks=blocks,
        heading=heading,
        chunk_index=chunk_index,
    )
