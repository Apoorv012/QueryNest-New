from ingest.loader import load_pdf
from ingest.extractor import extract_text_blocks
from ingest.normalizer import merge_spans_to_paragraphs
from ingest.cleanup import remove_headers_and_footers

from ingest.cleanup import PAGE_NUMBER_RE

doc = load_pdf("tests/fixtures/sample.pdf")
spans = extract_text_blocks(doc)
paragraphs = merge_spans_to_paragraphs(spans)
cleaned = remove_headers_and_footers(paragraphs)

for i, para in enumerate(paragraphs):
    if (para.text.lower() == '2'):
        print(f"para #{i}", para, "\n", sep="\n")
        

print("page 2", PAGE_NUMBER_RE.match("page 2"))
print("2", PAGE_NUMBER_RE.match("2"))
print("two", PAGE_NUMBER_RE.match("two"))