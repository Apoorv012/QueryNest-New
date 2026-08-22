"""Describe the eval corpus so it is verifiable without shipping the bytes.

Only 10 of the 18 corpus documents can be re-downloaded (see
`download_pdfs.py`); the rest are local and not redistributable. A metric is
meaningless without knowing which corpus produced it, so the manifest records
every document's hash, page count and family — enough for anyone to confirm
they are evaluating the identical corpus, or to see precisely how theirs
differs.

    python -m core.eval.corpus_manifest            # regenerate
    python -m core.eval.corpus_manifest --verify   # check disk against manifest

`--verify` exits non-zero on drift. A stale manifest is worse than none: it
would confidently describe a corpus that no longer exists, which is the same
failure mode as the mislabeled document it exists to catch.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pymupdf  # type: ignore[import-untyped]

CORPUS_DIR = Path("data/eval/pdfs")
MANIFEST_PATH = Path("data/eval/corpus_manifest.json")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _downloadable_names() -> set[str]:
    from core.eval.download_pdfs import PDFS

    return {entry["name"] for entry in PDFS}


def build_manifest() -> dict:
    downloadable = _downloadable_names()
    documents = []
    for path in sorted(CORPUS_DIR.rglob("*.pdf")):
        doc = pymupdf.open(path)
        page_count = len(doc)
        doc.close()
        documents.append({
            "filename": path.name,
            "family": path.parent.name,
            "sha256": _sha256(path),
            "page_count": page_count,
            "bytes": path.stat().st_size,
            # "download_pdfs" documents can be reconstructed from the repo;
            # "local" ones cannot, and are described here only.
            "source": "download_pdfs" if path.name in downloadable else "local",
        })
    reconstructible = sum(1 for d in documents if d["source"] == "download_pdfs")
    return {
        "document_count": len(documents),
        "reconstructible_from_repo": reconstructible,
        "local_only": len(documents) - reconstructible,
        "documents": documents,
    }


def write_manifest() -> dict:
    manifest = build_manifest()
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def verify_manifest() -> list[str]:
    """Return a list of drift descriptions; empty means the corpus matches."""
    if not MANIFEST_PATH.exists():
        return [f"manifest missing: {MANIFEST_PATH} (run without --verify to create it)"]

    recorded = {d["filename"]: d for d in json.loads(
        MANIFEST_PATH.read_text(encoding="utf-8"))["documents"]}
    actual = {d["filename"]: d for d in build_manifest()["documents"]}

    drift = []
    for name in sorted(recorded.keys() - actual.keys()):
        drift.append(f"MISSING  {name} — in manifest but not on disk")
    for name in sorted(actual.keys() - recorded.keys()):
        drift.append(f"EXTRA    {name} — on disk but not in manifest")
    for name in sorted(recorded.keys() & actual.keys()):
        if recorded[name]["sha256"] != actual[name]["sha256"]:
            drift.append(f"CHANGED  {name} — content differs from manifest")
    return drift


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    if "--verify" in sys.argv[1:]:
        drift = verify_manifest()
        if drift:
            print(f"Corpus drift detected ({len(drift)} issue(s)):")
            for line in drift:
                print(f"  {line}")
            sys.exit(1)
        print("Corpus matches the manifest.")
        return

    manifest = write_manifest()
    print(f"Wrote {MANIFEST_PATH}")
    print(f"  {manifest['document_count']} documents")
    print(f"  {manifest['reconstructible_from_repo']} reconstructible via download_pdfs")
    print(f"  {manifest['local_only']} local-only (described here, not redistributable)")


if __name__ == "__main__":
    main()
