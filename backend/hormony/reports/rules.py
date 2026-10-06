"""Offline, rule-based reading of text lab reports (used by the demo engine and as a fallback).

It only keeps lines whose test name it recognises, so it misses unusual layouts rather than inventing rows.
"""
from __future__ import annotations

import re
from typing import List, Optional

from .analytes import normalize

_LINE = re.compile(
    r"^(?P<name>[A-Za-z][A-Za-z0-9 ,()'./-]*?)[\s:]+(?P<cmp>[<>])?\s*(?P<value>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>(?:[a-zA-Zµμ%][a-zA-Zµμ%0-9^*.]*)(?:/[a-zA-Z0-9.]+)?)?"
    r"(?:\s+(?P<ref>\d+(?:[.,]\d+)?\s*[-–]\s*\d+(?:[.,]\d+)?|[<>]\s*\d+(?:[.,]\d+)?))?"
    r"(?:\s+(?P<flag>H|L|High|Low|HIGH|LOW))?\s*$")
_DATE_NEAR = re.compile(
    r"(collect(?:ed|ion)|sample|drawn|specimen|report(?:ed)?|date)[^\n\d]{0,25}"
    r"(\d{4}-\d{2}-\d{2}|\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9},?\s+\d{4}|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})",
    re.I)


def parse_date(text: str) -> Optional[str]:
    from dateutil import parser
    try:
        iso_like = re.fullmatch(r"\d{4}-\d{2}-\d{2}", text.strip())
        return parser.parse(text, dayfirst=not iso_like).date().isoformat()
    except (ValueError, OverflowError):
        return None


def find_collected_date(text: str) -> Optional[str]:
    for m in _DATE_NEAR.finditer(text):
        d = parse_date(m.group(2))
        if d:
            return d
    return None


def extract_rules(pages: List[str]):
    from .extract import ReportExtraction, ReportRow
    rows, seen = [], set()
    for page_no, text in enumerate(pages, start=1):
        for raw in text.splitlines():
            m = _LINE.match(raw.strip())
            if not m:
                continue
            code, name = normalize(m["name"])
            if code is None or code in seen:
                continue
            seen.add(code)
            flag = (m["flag"] or "")[:1].upper()
            rows.append(ReportRow(analyte=name, value=float(m["value"].replace(",", ".")), unit=m["unit"] or "",
                                  reference_range=(m["ref"] or "").replace(" ", ""), flag=flag or (m["cmp"] or ""),
                                  page=page_no))
    return ReportExtraction(collected_date=find_collected_date("\n".join(pages)) or "", lab_name="", results=rows)
