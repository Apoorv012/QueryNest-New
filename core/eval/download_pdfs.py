from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

import requests

PDFS: list[dict[str, str]] = [
    # Academic Papers (arXiv) — all tested OK
    {
        "category": "academic",
        "name": "attention_2017.pdf",
        "url": "https://arxiv.org/pdf/1706.03762.pdf",
        "year": "2017",
    },
    {
        "category": "academic",
        "name": "bert_2018.pdf",
        "url": "https://arxiv.org/pdf/1810.04805.pdf",
        "year": "2018",
    },
    {
        "category": "academic",
        "name": "gpt3_2020.pdf",
        "url": "https://arxiv.org/pdf/2005.14165.pdf",
        "year": "2020",
    },
    {
        "category": "academic",
        "name": "vit_2020.pdf",
        "url": "https://arxiv.org/pdf/2010.11929.pdf",
        "year": "2020",
    },
    {
        "category": "academic",
        "name": "rag_2020.pdf",
        "url": "https://arxiv.org/pdf/2005.11401.pdf",
        "year": "2020",
    },
    {
        "category": "academic",
        "name": "chain_of_thought_2022.pdf",
        "url": "https://arxiv.org/pdf/2201.11903.pdf",
        "year": "2022",
    },
    {
        "category": "academic",
        "name": "llama_2023.pdf",
        "url": "https://arxiv.org/pdf/2302.13971.pdf",
        "year": "2023",
    },
    {
        "category": "academic",
        "name": "mixture_of_experts_2024.pdf",
        "url": "https://arxiv.org/pdf/2404.04443.pdf",
        "year": "2024",
    },
    # Accounting Reports
    {
        "category": "accounting",
        "name": "berkshire_2022.pdf",
        "url": "https://www.berkshirehathaway.com/letters/2022ltr.pdf",
        "year": "2022",
    },
    {
        "category": "accounting",
        "name": "berkshire_2023.pdf",
        "url": "https://www.berkshirehathaway.com/letters/2023ltr.pdf",
        "year": "2023",
    },
    {
        "category": "accounting",
        "name": "berkshire_2024.pdf",
        "url": "https://www.berkshirehathaway.com/2024ar/2024ar.pdf",
        "year": "2024",
    },
    {
        "category": "accounting",
        "name": "gsk_2024.pdf",
        "url": "https://www.gsk.com/media/wrvfwob1/annual-report-2024.pdf",
        "year": "2024",
    },
    {
        "category": "accounting",
        "name": "unilever_2024.pdf",
        "url": "https://www.unilever.com/files/unilever-annual-report-and-accounts-2024.pdf",
        "year": "2024",
    },
    {
        "category": "accounting",
        "name": "ppl_2024.pdf",
        "url": "https://filecache.investorroom.com/mr5ir_pplweb2/1207/PPL_2024_Annual_Report.pdf",
        "year": "2024",
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


def download(pdf: dict[str, str]) -> bool:
    dest = BASE_DIR / pdf["category"] / pdf["name"]
    if dest.exists():
        print(f"  skip  {pdf['name']} (already exists)")
        return True
    try:
        r = requests.get(pdf["url"], timeout=30, allow_redirects=True)
        if r.status_code == 200 and len(r.content) > 1000:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(r.content)
            size_kb = len(r.content) / 1024
            print(f"  ok    {pdf['name']} ({size_kb:.0f} KB)")
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
