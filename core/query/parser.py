from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class ParsedQuery:
    query: str
    date_from: date | None = None
    date_to: date | None = None


_RELATIVE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\blast\s+(\d+)\s+months?\b", re.IGNORECASE), "months"),
    (re.compile(r"\bpast\s+(\d+)\s+months?\b", re.IGNORECASE), "months"),
    (re.compile(r"\blast\s+(\d+)\s+years?\b", re.IGNORECASE), "years"),
    (re.compile(r"\bpast\s+(\d+)\s+years?\b", re.IGNORECASE), "years"),
    (re.compile(r"\blast\s+year\b", re.IGNORECASE), "year"),
    (re.compile(r"\bpast\s+year\b", re.IGNORECASE), "year"),
    (re.compile(r"\blast\s+month\b", re.IGNORECASE), "month"),
    (re.compile(r"\bpast\s+month\b", re.IGNORECASE), "month"),
]

_EXACT_YEAR = re.compile(r"\bin\s+(\d{4})\b", re.IGNORECASE)
_RANGE_INCLUSIVE = re.compile(r"\bfrom\s+(\d{4})\s+to\s+(\d{4})\b", re.IGNORECASE)
_RANGE_DASH = re.compile(r"\b(\d{4})\s*[-–]\s*(\d{4})\b")
_BEFORE_YEAR = re.compile(r"\bbefore\s+(\d{4})\b", re.IGNORECASE)
_AFTER_YEAR = re.compile(r"\bafter\s+(\d{4})\b", re.IGNORECASE)


def _clean(query: str, *patterns: re.Pattern[str]) -> str:
    cleaned = query
    for p in patterns:
        cleaned = p.sub("", cleaned)
    return re.sub(r"\s{2,}", " ", cleaned).strip()


def parse_query(query: str) -> ParsedQuery:
    today = date.today()  # noqa: DTZ011

    for pattern, unit in _RELATIVE_PATTERNS:
        m = pattern.search(query)
        if m:
            if unit == "year":
                n = 1
            else:
                n = int(m.group(1))
            if unit in ("month", "months"):
                from_date = today - timedelta(days=n * 30)
            else:
                from_date = today - timedelta(days=n * 365)
            cleaned = _clean(query, pattern)
            return ParsedQuery(query=cleaned, date_from=from_date, date_to=today)

    m = _EXACT_YEAR.search(query)
    if m:
        year = int(m.group(1))
        cleaned = _clean(query, _EXACT_YEAR)
        return ParsedQuery(
            query=cleaned,
            date_from=date(year, 1, 1),
            date_to=date(year, 12, 31),
        )

    m = _RANGE_INCLUSIVE.search(query)
    if m:
        y1, y2 = int(m.group(1)), int(m.group(2))
        cleaned = _clean(query, _RANGE_INCLUSIVE)
        return ParsedQuery(
            query=cleaned,
            date_from=date(y1, 1, 1),
            date_to=date(y2, 12, 31),
        )

    m = _RANGE_DASH.search(query)
    if m:
        y1, y2 = int(m.group(1)), int(m.group(2))
        cleaned = _clean(query, _RANGE_DASH)
        return ParsedQuery(
            query=cleaned,
            date_from=date(y1, 1, 1),
            date_to=date(y2, 12, 31),
        )

    m = _BEFORE_YEAR.search(query)
    if m:
        year = int(m.group(1))
        cleaned = _clean(query, _BEFORE_YEAR)
        return ParsedQuery(
            query=cleaned,
            date_to=date(year - 1, 12, 31),
        )

    m = _AFTER_YEAR.search(query)
    if m:
        year = int(m.group(1))
        cleaned = _clean(query, _AFTER_YEAR)
        return ParsedQuery(
            query=cleaned,
            date_from=date(year + 1, 1, 1),
        )

    return ParsedQuery(query=query)
