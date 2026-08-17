"""
QueryNest CLI — PDF extraction demo.

Usage:
    python -m core.main                     # extract sample PDF
    python -m core.main <pdf_path>          # extract a PDF
"""

import sys

sys.stdout.reconfigure(encoding="utf-8")

from core.ingest.extractor import extract
from core.chunking.chunker import chunk_document


def main():
    args = sys.argv[1:]
    pdf_path = args[0] if args else "tests/fixtures/sample.pdf"

    doc = extract(pdf_path)
    chunks = chunk_document(doc)

    print(f"File: {doc.filename}")
    print(f"Pages: {len(doc.pages)}")
    print(f"Chunks: {len(chunks)}")
    print()

    for chunk in chunks[:5]:
        print(f"--- Chunk {chunk.chunk_index} [{chunk.heading}] ({len(chunk.source_blocks)} blocks) ---")
        print(f"  {chunk.text[:150]}...")
        print()
    if len(chunks) > 5:
        print(f"... +{len(chunks) - 5} more chunks")


if __name__ == "__main__":
    main()
