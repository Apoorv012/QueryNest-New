from __future__ import annotations

from core.index.config import get_storage_mode

from .base import FileStore
from .local import LocalFileStore
from .supabase import SupabaseFileStore

_cached_store: FileStore | None = None


def get_file_store() -> FileStore:
    global _cached_store
    if _cached_store is None:
        _cached_store = (
            LocalFileStore() if get_storage_mode() == "local" else SupabaseFileStore()
        )
    return _cached_store
