"""Turn an uploaded lab report into reviewable rows.

    text PDF         -> local text extraction -> text LLM (or rules for the demo engine / when the LLM is unavailable)
    photo / scan PDF -> page images           -> vision LLM
Nothing here writes to the ledger; the user confirms the rows first.
"""
from __future__ import annotations

import math
from datetime import date as Date
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field

from ..agents.llm import AgentUnavailable
from . import pdf
from .analytes import normalize
from .rules import extract_rules, parse_date

MAX_TEXT_CHARS = 24000

SYSTEM = ("[report] You read laboratory reports. Extract every test result that has a numeric value. Copy the test "
          "name, value, unit and reference range exactly as printed; do not convert units or guess missing values. "
          "`flag` is H or L only when the report marks the result high or low. `page` is the page the result is on. "
          "`collected_date` is the sample collection date as YYYY-MM-DD, or empty if it isn't printed.")


class ReportRow(BaseModel):
    analyte: str = Field(description="Test name exactly as printed")
    value: float
    unit: str = ""
    reference_range: str = ""
    flag: str = Field("", description="H, L or empty")
    page: int = 1


class ReportExtraction(BaseModel):
    collected_date: str = Field("", description="Sample collection date as YYYY-MM-DD, empty if not printed")
    lab_name: str = ""
    results: List[ReportRow] = []


class UnsupportedFile(Exception):
    pass


class NeedsVision(Exception):
    pass


PDF_TYPES = {"application/pdf"}
IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}


def kind_of(filename: str, content_type: str) -> str:
    name, ctype = (filename or "").lower(), (content_type or "").lower()
    if ctype in PDF_TYPES or name.endswith(".pdf"):
        return "pdf"
    if ctype in IMAGE_TYPES or name.endswith((".png", ".jpg", ".jpeg", ".webp")):
        return "image"
    if ctype in ("image/heic", "image/heif") or name.endswith((".heic", ".heif")):
        raise UnsupportedFile("HEIC photos aren't supported yet; export the photo as JPEG or PNG and try again")
    raise UnsupportedFile("upload a PDF or a photo (JPEG, PNG or WebP)")


UNREADABLE = ("Hormony couldn't open this file. It may be damaged, password-protected, or in a format such as HEIC. "
              "Try a PDF, JPEG or PNG.")


def _open(fn, data: bytes):
    """Decode an upload; a file the libraries can't parse is a bad upload (415), not a server error."""
    try:
        return fn(data)
    except Exception as e:  # pypdf, pypdfium2 and Pillow each raise their own error types for broken input
        raise UnsupportedFile(UNREADABLE) from e


async def read_report(data: bytes, filename: str, content_type: str, text_llm, vision_llm) -> Tuple[ReportExtraction, str, int, List[str]]:
    """Returns (extraction, method, pages, warnings)."""
    warnings: List[str] = []
    if kind_of(filename, content_type) == "pdf":
        texts = _open(pdf.page_texts, data)
        if pdf.has_text_layer(texts):
            if getattr(text_llm, "name", "") == "demo":
                return extract_rules(texts), "rules", len(texts), warnings
            joined = "\n\n".join(f"=== Page {i} ===\n{t}" for i, t in enumerate(texts, start=1))[:MAX_TEXT_CHARS]
            try:
                return await text_llm.structured(SYSTEM, joined, ReportExtraction, effort="low"), "text", len(texts), warnings
            except AgentUnavailable:
                warnings.append("The AI reader was unavailable, so basic parsing was used. Please check every value.")
                return extract_rules(texts), "rules", len(texts), warnings
        images, pages = _open(pdf.render_pages, data), len(texts)
        if pages > pdf.MAX_VISION_PAGES:
            warnings.append(f"Only the first {pdf.MAX_VISION_PAGES} of {pages} pages were read.")
    else:
        images, pages = [_open(pdf.prepare_image, data)], 1
    if vision_llm is None:
        raise NeedsVision("This is a photo or a scanned PDF. Reading it needs OPENROUTER_API_KEY (and optionally "
                          "HORMONY_VISION_MODEL) in backend/.env")
    out = await vision_llm.structured_vision(SYSTEM, "Extract the lab results from these report pages.", images,
                                             ReportExtraction, effort="low")
    return out, "vision", pages, warnings


def review_rows(extraction: ReportExtraction, today: Date) -> Tuple[List[dict], str, List[str]]:
    """Normalise names, attach a date to every row, and flag anything the user should double-check."""
    warnings: List[str] = []
    collected = parse_date(extraction.collected_date) if extraction.collected_date else None
    if not collected:
        warnings.append("No collection date was found. Set the date before saving.")
    elif Date.fromisoformat(collected) > today:
        warnings.append(f"The collection date {collected} is after today. Please check it.")
    rows, seen = [], set()
    for r in extraction.results:
        if r.value is None or not math.isfinite(r.value):
            continue
        code, name = normalize(r.analyte)
        key = (code or name.lower(), r.value)
        if key in seen:
            continue
        seen.add(key)
        rows.append({"analyte": name, "code": code, "printed_name": r.analyte, "value": r.value,
                     "unit": (r.unit or "").strip()[:20], "reference_range": (r.reference_range or "").strip()[:40],
                     "flag": (r.flag or "").strip()[:2].upper(), "page": max(1, int(r.page or 1)), "date": collected or ""})
    if not rows:
        warnings.append("No test results were recognised in this file.")
    return rows, collected or "", warnings
