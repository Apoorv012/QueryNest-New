from __future__ import annotations

import re
from datetime import date


def extract_date_from_filename(filename: str) -> date | None:
    match = re.search(r"(\d{4})", filename)
    if match:
        year = int(match.group(1))
        if 1900 <= year <= 2100:
            return date(year, 1, 1)
    return None


def extract_date_from_metadata(metadata: dict) -> date | None:
    raw = metadata.get("creationDate") or metadata.get("modDate")
    if not raw:
        return None
    match = re.search(r"(\d{4})(\d{2})(\d{2})", raw)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            pass
    match = re.search(r"(\d{4})", raw)
    if match:
        year = int(match.group(1))
        if 1900 <= year <= 2100:
            return date(year, 1, 1)
    return None


def extract_date_from_text(text: str) -> date | None:
    patterns = [
        r"(?:published|dated?|issued|copyright)\s*(?:in|on|:)?\s*(\w+\s+\d{1,2},?\s*\d{4})",
        r"(?:published|dated?|issued|copyright)\s*(?:in|on|:)?\s*(\d{1,2}\s+\w+\s+\d{4})",
        r"(?:published|dated?|issued|copyright)\s*(?:in|on|:)?\s*(\w+\s+\d{4})",
        r"(?:published|dated?|issued|copyright)\s*(?:in|on|:)?\s*(\d{4})",
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b",
        r"\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw = match.group(0)
            year_match = re.search(r"(\d{4})", raw)
            if year_match:
                year = int(year_match.group(1))
                if 1900 <= year <= 2100:
                    return date(year, 1, 1)
    return None


def extract_date(
    filename: str,
    pdf_metadata: dict | None = None,
    first_page_text: str | None = None,
) -> tuple[date | None, str | None]:
    date_val = extract_date_from_filename(filename)
    if date_val:
        return date_val, "filename"

    if pdf_metadata:
        date_val = extract_date_from_metadata(pdf_metadata)
        if date_val:
            return date_val, "metadata"

    if first_page_text:
        date_val = extract_date_from_text(first_page_text)
        if date_val:
            return date_val, "content"

    return None, None
