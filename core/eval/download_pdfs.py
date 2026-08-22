"""Fetch the publicly-redistributable part of the eval corpus.

**This does NOT rebuild the whole corpus.** It fetches 10 of the 18 documents in
`data/eval/pdfs/`. The other 8 (the career-document family and
`sensors-25-03183.pdf`) came from a local, gitignored folder and are not
redistributable, so they cannot be downloaded here.

`data/eval/corpus_manifest.json` describes all 18 with hashes, so the corpus is
verifiable even where the bytes cannot be shipped. Regenerate and check it with
`python -m core.eval.corpus_manifest [--verify]`.

Each entry carries an `expect` keyword that must appear in the downloaded PDF's
text. That guard exists because `mixture_of_experts_2024.pdf` was for a long
time a 6G optical-wireless paper — the URL was simply wrong, nothing verified
it, and four golden queries were silently unanswerable as a result.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

import fitz  # type: ignore[import-untyped]  # PyMuPDF, transitive dep of pymupdf4llm
import requests

PDFS: list[dict[str, str]] = [
    {
        "category": "academic",
        "name": "attention_2017.pdf",
        "url": "https://arxiv.org/pdf/1706.03762.pdf",
        "year": "2017",
        "expect": "scaled dot-product",
    },
    {
        "category": "academic",
        "name": "bert_2018.pdf",
        "url": "https://arxiv.org/pdf/1810.04805.pdf",
        "year": "2018",
        "expect": "masked language",
    },
    {
        "category": "academic",
        "name": "vit_2020.pdf",
        "url": "https://arxiv.org/pdf/2010.11929.pdf",
        "year": "2020",
        "expect": "image patches",
    },
    {
        "category": "academic",
        "name": "rag_2020.pdf",
        "url": "https://arxiv.org/pdf/2005.11401.pdf",
        "year": "2020",
        "expect": "retrieval-augmented",
    },
    {
        "category": "academic",
        "name": "chain_of_thought_2022.pdf",
        "url": "https://arxiv.org/pdf/2201.11903.pdf",
        "year": "2022",
        "expect": "chain of thought",
    },
    {
        "category": "academic",
        "name": "llama_2023.pdf",
        "url": "https://arxiv.org/pdf/2302.13971.pdf",
        "year": "2023",
        "expect": "LLaMA",
    },
    {
        "category": "academic",
        "name": "mixture_of_experts_2024.pdf",
        "url": "https://arxiv.org/pdf/2401.04088.pdf",
        "year": "2024",
        "expect": "mixture of experts",
    },
    {
        "category": "academic",
        "name": "optical_wireless_6g_2024.pdf",
        "url": "https://arxiv.org/pdf/2404.04443.pdf",
        "year": "2024",
        "expect": "optical wireless",
    },
    {
        "category": "accounting",
        "name": "berkshire_2022.pdf",
        "url": "https://www.berkshirehathaway.com/letters/2022ltr.pdf",
        "year": "2022",
        "expect": "Berkshire Hathaway",
    },
    {
        "category": "accounting",
        "name": "berkshire_2023.pdf",
        "url": "https://www.berkshirehathaway.com/letters/2023ltr.pdf",
        "year": "2023",
        "expect": "Berkshire Hathaway",
    },
]

# Recorded, never downloaded. These exceed the ~45 page cap set by D10
# (see docs/decisions.md). They are kept here deliberately rather than
# deleted: without this record, someone re-adds gsk_2024.pdf, waits out a
# ~30 minute seed, and rediscovers the page cap from scratch. Re-enabling
# any of these grows the corpus from 18 to 23 documents and roughly
# triples re-seed time, shifting every baseline.
EXCLUDED_BY_D10: list[dict[str, str]] = [
    {
        "category": "academic",
        "name": "gpt3_2020.pdf",
        "url": "https://arxiv.org/pdf/2005.14165.pdf",
        "year": "2020",
        "expect": "few-shot",
    },
    {
        "category": "accounting",
        "name": "berkshire_2024.pdf",
        "url": "https://www.berkshirehathaway.com/2024ar/2024ar.pdf",
        "year": "2024",
        "expect": "Berkshire Hathaway",
    },
    {
        "category": "accounting",
        "name": "gsk_2024.pdf",
        "url": "https://www.gsk.com/media/wrvfwob1/annual-report-2024.pdf",
        "year": "2024",
        "expect": "GSK",
    },
    {
        "category": "accounting",
        "name": "unilever_2024.pdf",
        "url": "https://www.unilever.com/files/unilever-annual-report-and-accounts-2024.pdf",
        "year": "2024",
        "expect": "Unilever",
    },
    {
        "category": "accounting",
        "name": "ppl_2024.pdf",
        "url": "https://filecache.investorroom.com/mr5ir_pplweb2/1207/PPL_2024_Annual_Report.pdf",
        "year": "2024",
        "expect": "PPL",
    },
]

BASE_DIR = Path("data/eval/pdfs")


def test_url(url: str) -> tuple[bool, int, str]:
    try:
        r = requests.head(url, timeout=10, allow_redirects=True)
        ct = r.headers.get("content-type", "")
        if r.status_code == 200 and ("pdf" in ct or "octet" in ct or url.endswith(".pdf")):
            return True, r.status_code, ct
        return False, r.status_code, ct
    except requests.RequestException as e:
        return False, 0, str(e)


def verify_content(path: Path, expect: str, pages_to_scan: int = 5) -> bool:
    """Check that `expect` (case-insensitive) appears somewhere in the PDF's first
    few pages of extracted text. This is the guard against a URL silently resolving
    to the wrong document (e.g. a withdrawn/replaced/renumbered arXiv paper) — see
    the `mixture_of_experts_2024.pdf` incident recorded above `optical_wireless_6g_2024.pdf`.
    """
    doc = fitz.open(path)
    try:
        text = "".join(doc[i].get_text() for i in range(min(pages_to_scan, len(doc))))
    finally:
        doc.close()
    return expect.lower() in text.lower()


def download(pdf: dict[str, str]) -> bool:
    dest = BASE_DIR / pdf["category"] / pdf["name"]
    expect = pdf.get("expect")

    if dest.exists():
        if expect and not verify_content(dest, expect):
            print(
                f"  FAIL  {pdf['name']} (already on disk but does NOT contain "
                f"expected text {expect!r} — wrong file? re-download or investigate)"
            )
            return False
        print(f"  skip  {pdf['name']} (already exists, content verified)")
        return True

    try:
        r = requests.get(pdf["url"], timeout=30, allow_redirects=True)
        if r.status_code == 200 and len(r.content) > 1000:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(r.content)
            size_kb = len(r.content) / 1024

            if expect and not verify_content(dest, expect):
                dest.unlink()  # do not leave a mis-verified file on disk
                print(
                    f"  FAIL  {pdf['name']} downloaded ({size_kb:.0f} KB) but does NOT "
                    f"contain expected text {expect!r} — URL likely resolves to the "
                    f"wrong document. File removed; fix the URL before retrying."
                )
                return False

            verified = " (content verified)" if expect else ""
            print(f"  ok    {pdf['name']} ({size_kb:.0f} KB){verified}")
            return True
        print(f"  FAIL  {pdf['name']} (status={r.status_code}, size={len(r.content)})")
        return False
    except requests.RequestException as e:
        print(f"  FAIL  {pdf['name']} ({e})")
        return False


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("Testing URLs...\n")
        for pdf in PDFS:
            ok, status, ct = test_url(pdf["url"])
            mark = "OK" if ok else "FAIL"
            print(f"  {mark}  [{pdf['year']}] {pdf['category']}/{pdf['name']}")
            print(f"      {pdf['url']}")
            print(f"      status={status}  content-type={ct}\n")
        return

    print("Downloading PDFs...\n")
    ok = 0
    fail = 0
    for pdf in PDFS:
        if download(pdf):
            ok += 1
        else:
            fail += 1
    print(f"\nDone: {ok} downloaded, {fail} failed")


if __name__ == "__main__":
    main()
