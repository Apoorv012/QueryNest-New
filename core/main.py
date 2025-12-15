from core.ingest.loader import load_pdf
from core.ingest.extractor import extract_text_blocks
from core.ingest.normalizer import merge_spans_to_lines, merge_lines_to_paragraphs
from core.ingest.cleanup import remove_headers_and_footers
from core.chunking.chunker import chunk_paragraph

doc = load_pdf("tests/fixtures/sample.pdf")
spans = extract_text_blocks(doc)

lines = merge_spans_to_lines(spans)
paragraphs = merge_lines_to_paragraphs(lines)
cleaned = remove_headers_and_footers(paragraphs)

chunks = chunk_paragraph(cleaned)

# for i, para in enumerate(cleaned[10:20]):
#     print(f"para #{i}", para, "\n", sep="\n")

# print("para len:", len(paragraphs))
# print("cleaned len:", len(cleaned))

print("Total chunks:", len(chunks))
for i, c in enumerate(chunks[:5]):
    print("=" * 50)
    print(f"Chunk {i}")
    print(c.text)
    print("Pages:", c.pages)

