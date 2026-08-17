
from core.models.chunk import Chunk

_documents: dict[str, dict] = {}


def save_document(doc_id: str, filename: str, chunks: list[Chunk]) -> None:
    _documents[doc_id] = {
        "filename": filename,
        "chunks": chunks,
    }


def get_chunks(doc_id: str) -> list[Chunk] | None:
    doc = _documents.get(doc_id)
    if doc is None:
        return None
    return doc["chunks"]


def get_filename(doc_id: str) -> str | None:
    doc = _documents.get(doc_id)
    if doc is None:
        return None
    return doc["filename"]
