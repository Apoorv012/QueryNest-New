
from core.models.chunk import Chunk
from core.models.extracted import ExtractedBlock, ExtractedDocument

from .tokenizer import estimate_tokens

MAX_TOKENS = 400
MIN_TOKENS = 120


def chunk_document(doc: ExtractedDocument) -> list[Chunk]:
    blocks = [
        b for page in doc.pages for b in page.blocks
    ]
    return _chunk_blocks(blocks)


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
