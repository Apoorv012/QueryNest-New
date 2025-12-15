import re

# Matches: "1", "2.3", "4.1.2 Title"
NUMBERED_HEADING_RE = re.compile(r"^\d+(\.\d+)*\s+.+")
ROMAN_HEADING_RE = re.compile(r"^(I|II|III|IV|V|VI|VII|VIII|IX|X)\.?\s+.+", re.I)

MAX_HEADING_LENGTH = 40


def is_heading(text: str) -> bool:
    t = text.strip()

    if not t:
        return False

    # Too long → probably body text
    if len(t) > MAX_HEADING_LENGTH:
        return False

    # Numbered headings
    if NUMBERED_HEADING_RE.match(t):
        return True

    # Roman numeral headings
    if ROMAN_HEADING_RE.match(t):
        return True

    # ALL CAPS short headings
    if t.isupper() and len(t.split()) <= 5:
        return True

    return False
