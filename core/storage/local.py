from __future__ import annotations

from pathlib import Path

from .base import FileStore

# Shared with tests/api/test_api.py, which plants decoy files at
# UPLOAD_DIR.parent to verify a traversal user_id can't escape this directory.
UPLOAD_DIR = Path("data/uploads").resolve()


class LocalFileStore(FileStore):
    def _path(self, user_id: str, doc_id: str) -> Path:
        pdf_dir = (UPLOAD_DIR / user_id).resolve()
        if not pdf_dir.is_relative_to(UPLOAD_DIR):
            raise ValueError(f"Invalid user_id: {user_id!r}")
        return pdf_dir / f"{doc_id}.pdf"

    def save(self, user_id: str, doc_id: str, data: bytes) -> None:
        path = self._path(user_id, doc_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, user_id: str, doc_id: str) -> bytes:
        path = self._path(user_id, doc_id)
        if not path.exists():
            raise FileNotFoundError(doc_id)
        return path.read_bytes()

    def delete(self, user_id: str, doc_id: str) -> None:
        try:
            self._path(user_id, doc_id).unlink(missing_ok=True)
        except ValueError:
            pass

    def delete_all(self, user_id: str) -> None:
        pdf_dir = (UPLOAD_DIR / user_id).resolve()
        if not pdf_dir.is_relative_to(UPLOAD_DIR) or not pdf_dir.is_dir():
            return
        for pdf in pdf_dir.glob("*.pdf"):
            pdf.unlink(missing_ok=True)
