"""
QueryNest CLI — PDF extraction demo.

Usage:
    python -m core.main                     # extract sample PDF
    python -m core.main <pdf_path>          # extract a PDF
"""

import sys

sys.stdout.reconfigure(encoding="utf-8")

from core.ingest.extractor import extract


def main():
    args = sys.argv[1:]
    pdf_path = args[0] if args else "tests/fixtures/sample.pdf"

    doc = extract(pdf_path)

    print(f"File: {doc.filename}")
    print(f"Pages: {len(doc.pages)}")
    print()

    for page in doc.pages[:3]:
        print(f"--- Page {page.page_number} ({len(page.blocks)} blocks) ---")
        for b in page.blocks[:5]:
            print(f"  [{b.type}] {b.text[:120]}")
        if len(page.blocks) > 5:
            print(f"  ... +{len(page.blocks) - 5} more blocks")
        print()


if __name__ == "__main__":
    main()
