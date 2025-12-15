from ingest.loader import load_pdf
from ingest.extractor import extract_text_blocks
from ingest.normalizer import merge_spans_to_paragraphs
from ingest.cleanup import remove_headers_and_footers

doc = load_pdf("tests/fixtures/sample.pdf")
spans = extract_text_blocks(doc)
paragraphs = merge_spans_to_paragraphs(spans)
cleaned = remove_headers_and_footers(paragraphs)

c = 15
cnt = 0
cntLong = 0
totLongLen = 0
mi, ma = 1e9, 0
for i, para in enumerate(cleaned):
    if (len(para.text) < 10):
        if c:
            c -= 1
            print(f"para #{i}", para, "\n", sep="\n")
        cnt += 1
    else:
        totLongLen += len(para.text)
        cntLong += 1
        mi = min(mi, len(para.text))
        ma = max(ma, len(para.text))


print(cnt, len(cleaned))
print("Average:", totLongLen / cntLong)
print(mi, ma)
# print(len(paragraphs), len(cleaned))