from abc import ABC, abstractmethod


class FileStore(ABC):
    """Where uploaded PDF bytes live, independent of the vector store.

    Mirrors core/index/base.py's VectorStore split: one interface, a local
    implementation and a hosted one, picked by QUERYNEST_STORAGE_MODE.
    """

    @abstractmethod
    def save(self, user_id: str, doc_id: str, data: bytes) -> None: ...

    @abstractmethod
    def get(self, user_id: str, doc_id: str) -> bytes | str:
        """Return the PDF's raw bytes (local) or a signed URL to it (hosted).

        Raises FileNotFoundError if no such document is stored.
        """
        ...

    @abstractmethod
    def delete(self, user_id: str, doc_id: str) -> None:
        """Best-effort remove; must not raise if the file is already gone."""
        ...

    @abstractmethod
    def delete_all(self, user_id: str) -> None:
        """Best-effort remove every file stored for this user."""
        ...
