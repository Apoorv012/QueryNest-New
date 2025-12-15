from typing import List
from .heading import is_heading
from .tokenizer import estimate_tokens
from core.models.chunk import Chunk
from core.models.text_block import TextBlock

MAX_TOKENS = 400
MIN_TOKENS = 120


def chunk_paragraph(paragraph: List[TextBlock]) -> List[Chunk]:
    chunks: List[Chunk] = []
    
    current_text = []
    current_pages = set()
    current_bboxes = []
    current_tokens = 0

    for p in paragraph:
        text = p.text
        tokens = estimate_tokens(text)
        
        if is_heading(text) and current_tokens >= MIN_TOKENS:
            chunks.append(
                Chunk(
                    text="\n".join(current_text),
                    pages=sorted(current_pages),
                    bboxes=current_bboxes
                )
            )
            current_text = []
            current_pages = set()
            current_bboxes = []
            current_tokens = 0
            
        if current_tokens + tokens > MAX_TOKENS and current_tokens >= MIN_TOKENS:
            chunks.append(
                Chunk(
                    text="\n".join(current_text),
                    pages=sorted(current_pages),
                    bboxes=current_bboxes
                )
            )
            current_text = []
            current_pages = set()
            current_bboxes = []
            current_tokens = 0
        
        current_text.append(text)
        current_pages.add(p.page)
        current_bboxes.append(p.bbox)
        current_tokens += tokens
        
    if current_text:
        chunks.append(
            Chunk(
                text="\n".join(current_text),
                pages=sorted(current_pages),
                bboxes=current_bboxes
            )
        )

    return chunks
