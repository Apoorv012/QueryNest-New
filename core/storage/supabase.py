from __future__ import annotations

import os

import requests

from .base import FileStore

_TIMEOUT = 30


class SupabaseFileStore(FileStore):
    """PDF storage on the Supabase Storage REST API.

    Uses `requests` (already a dependency) directly against the REST API
    instead of adding the `supabase-py` SDK — the surface needed here is
    three calls (upload, sign, delete), not worth a new dependency for.
    """

    def __init__(self) -> None:
        self._base = os.environ["SUPABASE_URL"].rstrip("/")
        self._key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        self._bucket = os.environ.get("SUPABASE_STORAGE_BUCKET", "pdfs")

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._key}", "apikey": self._key}

    def _path(self, user_id: str, doc_id: str) -> str:
        return f"{user_id}/{doc_id}.pdf"

    def save(self, user_id: str, doc_id: str, data: bytes) -> None:
        url = f"{self._base}/storage/v1/object/{self._bucket}/{self._path(user_id, doc_id)}"
        headers = {**self._headers(), "Content-Type": "application/pdf", "x-upsert": "true"}
        resp = requests.post(url, headers=headers, data=data, timeout=_TIMEOUT)
        resp.raise_for_status()

    def get(self, user_id: str, doc_id: str) -> str:
        url = (
            f"{self._base}/storage/v1/object/sign/{self._bucket}/"
            f"{self._path(user_id, doc_id)}"
        )
        resp = requests.post(
            url, headers=self._headers(), json={"expiresIn": 3600}, timeout=_TIMEOUT
        )
        if resp.status_code == 404:
            raise FileNotFoundError(doc_id)
        resp.raise_for_status()
        return f"{self._base}/storage/v1{resp.json()['signedURL']}"

    def delete(self, user_id: str, doc_id: str) -> None:
        try:
            resp = requests.delete(
                f"{self._base}/storage/v1/object/{self._bucket}",
                headers=self._headers(),
                json={"prefixes": [self._path(user_id, doc_id)]},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
        except requests.RequestException:
            pass

    def delete_all(self, user_id: str) -> None:
        try:
            resp = requests.post(
                f"{self._base}/storage/v1/object/list/{self._bucket}",
                headers=self._headers(),
                json={"prefix": f"{user_id}/"},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            names = [f"{user_id}/{item['name']}" for item in resp.json()]
            if not names:
                return
            requests.delete(
                f"{self._base}/storage/v1/object/{self._bucket}",
                headers=self._headers(),
                json={"prefixes": names},
                timeout=_TIMEOUT,
            ).raise_for_status()
        except requests.RequestException:
            pass
