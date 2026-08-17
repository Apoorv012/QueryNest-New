import os
import uuid
from pathlib import Path

from fastapi import APIRouter, File, UploadFile

from core.chunking.chunker import chunk_document
from core.ingest.extractor import extract

from ..store import save_document

router = APIRouter()

_has_pgvector = bool(os.environ.get("QUERYNEST_DATABASE_URL"))


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

    indexed = False
    if _has_pgvector:
        try:
            from core.embedding import FastEmbedEmbedder
            from core.index import get_vector_store

            embedder = FastEmbedEmbedder()
            texts = [c.text for c in chunks]
            embeddings = embedder.embed(texts)

            store = get_vector_store()
            store.setup()
            store.store_chunks(
                document_id=doc_id,
                texts=texts,
                embeddings=embeddings,
                headings=[c.heading for c in chunks],
                pages=[c.source_blocks[0].page if c.source_blocks else 0 for c in chunks],
                chunk_indices=[c.chunk_index for c in chunks],
            )
            indexed = True
        except (RuntimeError, OSError):
            indexed = False

    return {
        "id": doc_id,
        "filename": file.filename,
        "pages": len(doc.pages),
        "chunk_count": len(chunks),
        "indexed": indexed,
    }
