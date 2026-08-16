from typing import List
from .heading import is_heading
from .tokenizer import estimate_tokens
from core.models.chunk import Chunk, Paragraph
from core.models.text_block import TextBlock

MAX_TOKENS = 400
MIN_TOKENS = 120


def chunk_paragraph(paragraphs: List[TextBlock]) -> List[Chunk]:
    chunks: List[Chunk] = []

    current_text = []
    current_paragraphs: List[Paragraph] = []
    current_tokens = 0

    for p in paragraphs:
        tokens = estimate_tokens(p.text)

        if is_heading(p.text) and current_tokens >= MIN_TOKENS:
            chunks.append(_flush(current_text, current_paragraphs))
            current_text = []
            current_paragraphs = []
            current_tokens = 0

        if current_tokens + tokens > MAX_TOKENS and current_tokens >= MIN_TOKENS:
            chunks.append(_flush(current_text, current_paragraphs))
            current_text = []
            current_paragraphs = []
            current_tokens = 0

        current_text.append(p.text)
        current_paragraphs.append(
            Paragraph(text=p.text, page=p.page, bbox=p.bbox)
        )
        current_tokens += tokens

    if current_text:
        chunks.append(_flush(current_text, current_paragraphs))

    return chunks


def _flush(text_lines: List[str], paragraphs: List[Paragraph]) -> Chunk:
    return Chunk(
        text="\n".join(text_lines),
        paragraphs=paragraphs,
    )
