"""
QueryNest CLI — Full pipeline demo.

Usage:
    python -m core.main                     # ingest sample + search demo
    python -m core.main ingest <pdf_path>   # ingest a PDF
    python -m core.main search <query>      # search indexed documents
"""

import sys
import os

from core.ingest.loader import load_pdf
from core.ingest.extractor import extract_text_blocks
from core.ingest.normalizer import merge_spans_to_lines, merge_lines_to_paragraphs
from core.ingest.cleanup import remove_headers_and_footers
from core.chunking.chunker import chunk_paragraph
from core.embedding.factory import get_embedder
from core.index.faiss_index import FaissIndex

# Default paths
INDEX_DIR = os.path.join(os.path.dirname(__file__), "..", ".querynest_data")
SAMPLE_PDF = "tests/fixtures/sample.pdf"


def ingest_pdf(pdf_path: str, index_dir: str = INDEX_DIR):
    """Full ingest pipeline: PDF -> chunks -> embeddings -> FAISS index."""

    print(f"[LOAD] Loading: {pdf_path}")
    doc = load_pdf(pdf_path)

    print(f"   Pages: {len(doc)}")

    # --- Extract & normalize ---
    spans = extract_text_blocks(doc)
    print(f"   Spans extracted: {len(spans)}")

    lines = merge_spans_to_lines(spans)
    paragraphs = merge_lines_to_paragraphs(lines)
    cleaned = remove_headers_and_footers(paragraphs)
    print(f"   Paragraphs (cleaned): {len(cleaned)}")

    # --- Chunk ---
    chunks = chunk_paragraph(cleaned)
    print(f"   Chunks: {len(chunks)}")

    # --- Embed ---
    print(f"[EMBED] Generating embeddings...")
    embedder = get_embedder()
    texts = [c.text for c in chunks]
    vectors = embedder.embed(texts)
    print(f"   Embedded: {vectors.shape[0]} chunks -> {vectors.shape[1]}-dim vectors")

    # --- Index ---
    print(f"[INDEX] Building FAISS index...")

    # Load existing index or create new
    if os.path.exists(os.path.join(index_dir, "index.faiss")):
        index = FaissIndex.load(index_dir)
        print(f"   Loaded existing index ({index.size} vectors)")
    else:
        index = FaissIndex(dim=embedder.dim)

    document_id = os.path.basename(pdf_path)
    index.add(vectors, document_id=document_id)
    index.save(index_dir)
    print(f"   Saved index ({index.size} total vectors) -> {index_dir}")

    # Store chunks for retrieval (simple JSON sidecar for now)
    import json
    chunks_path = os.path.join(index_dir, f"{document_id}_chunks.json")
    chunks_data = [
        {
            "text": c.text,
            "pages": c.pages,
            "bboxes": [list(b) for b in c.bboxes],
        }
        for c in chunks
    ]
    with open(chunks_path, "w", encoding="utf-8") as f:
        json.dump(chunks_data, f, indent=2)

    print(f"[DONE] Ingestion complete!")
    return chunks, vectors


def search_query(query: str, index_dir: str = INDEX_DIR, top_k: int = 5):
    """Search the FAISS index with a natural language query."""

    if not os.path.exists(os.path.join(index_dir, "index.faiss")):
        print("[ERROR] No index found. Run 'python -m core.main ingest <pdf>' first.")
        return

    print(f'[SEARCH] Searching: "{query}"')

    # Load index
    index = FaissIndex.load(index_dir)
    print(f"   Index loaded ({index.size} vectors)")

    # Embed query
    embedder = get_embedder()
    query_vector = embedder.embed_query(query)

    # Search
    hits = index.search(query_vector, top_k=top_k)

    # Load chunk text for display
    import json
    print(f"\n{'='*60}")
    print(f"Top {len(hits)} results:")
    print(f"{'='*60}")

    for i, hit in enumerate(hits):
        chunks_path = os.path.join(index_dir, f"{hit.document_id}_chunks.json")
        chunk_text = ""
        chunk_pages = []
        if os.path.exists(chunks_path):
            with open(chunks_path, "r", encoding="utf-8") as f:
                chunks_data = json.load(f)
            if hit.chunk_index < len(chunks_data):
                chunk_text = chunks_data[hit.chunk_index]["text"]
                chunk_pages = chunks_data[hit.chunk_index]["pages"]

        print(f"\n--- Result #{i+1} (score: {hit.score:.4f}) ---")
        print(f"Document: {hit.document_id}")
        print(f"Pages: {chunk_pages}")
        preview = chunk_text[:300].encode("ascii", errors="replace").decode("ascii")
        print(f"Text preview: {preview}...")
        print()


def main():
    args = sys.argv[1:]

    if not args:
        # Default: ingest sample PDF + demo search
        print("=" * 60)
        print("QueryNest - Full Pipeline Demo")
        print("=" * 60)
        print()

        ingest_pdf(SAMPLE_PDF)

        print()
        print("-" * 60)
        print()

        search_query("attention mechanism")

    elif args[0] == "ingest" and len(args) >= 2:
        ingest_pdf(args[1])

    elif args[0] == "search" and len(args) >= 2:
        query = " ".join(args[1:])
        search_query(query)

    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
