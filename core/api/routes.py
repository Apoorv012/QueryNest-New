import uuid
from pathlib import Path

from fastapi import APIRouter, File, UploadFile

from core.chunking.chunker import chunk_document
from core.ingest.extractor import extract

from .store import get_chunks, save_document

router = APIRouter()


@router.post("/upload")
def upload(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return {"error": "Only PDF files are accepted"}

    tmp_path = Path("tmp") / file.filename
    tmp_path.parent.mkdir(exist_ok=True)
    tmp_path.write_bytes(file.file.read())

    try:
        doc = extract(str(tmp_path))
        chunks = chunk_document(doc)
    finally:
        tmp_path.unlink(missing_ok=True)

    doc_id = uuid.uuid4().hex[:12]
    save_document(doc_id, file.filename, chunks)

    return {
        "id": doc_id,
        "filename": file.filename,
        "pages": len(doc.pages),
        "chunk_count": len(chunks),
    }


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
