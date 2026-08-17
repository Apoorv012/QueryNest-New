from fastapi import APIRouter

from ..store import get_chunks

router = APIRouter()


@router.get("/documents/{doc_id}/chunks")
def list_chunks(doc_id: str):
    chunks = get_chunks(doc_id)
    if chunks is None:
        return {"error": "Document not found"}

    return {
        "chunks": [
            {
                "chunk_index": c.chunk_index,
                "heading": c.heading,
                "text": c.text,
                "block_count": len(c.source_blocks),
                "blocks": [
                    {
                        "text": b.text,
                        "page": b.page,
                        "bbox": list(b.bbox),
                        "type": b.type,
                    }
                    for b in c.source_blocks
                ],
            }
            for c in chunks
        ]
    }
