import json

import pymupdf4llm

from core.models.extracted import ExtractedBlock, ExtractedPage, ExtractedDocument

CONTENT_TYPES = frozenset({
    "text",
    "section-header",
    "caption",
    "footnote",
    "list-item",
})


def extract(pdf_path: str) -> ExtractedDocument:
    raw = pymupdf4llm.to_json(pdf_path, page_chunks=False)
    data = json.loads(raw)

    pages = []
    for page in data["pages"]:
        blocks = []
        for box in page["boxes"]:
            if box["boxclass"] not in CONTENT_TYPES:
                continue

            text = " ".join(
                span["text"]
                for textline in box["textlines"]
                for span in textline["spans"]
            ).strip()

            if not text:
                continue

            blocks.append(ExtractedBlock(
                text=text,
                page=page["page_number"] - 1,
                bbox=(box["x0"], box["y0"], box["x1"], box["y1"]),
                type=box["boxclass"],
            ))

        pages.append(ExtractedPage(
            page_number=page["page_number"],
            width=page["width"],
            height=page["height"],
            blocks=blocks,
        ))

    return ExtractedDocument(
        filename=data["filename"],
        pages=pages,
    )
