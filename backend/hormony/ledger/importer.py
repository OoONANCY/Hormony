"""CSV/JSON importer with provenance. Idempotent by deterministic IDs."""
from __future__ import annotations

from datetime import date as Date
from typing import Optional
from pydantic import BaseModel

from ..config import settings
from ..db import SessionLocal
from ..models import Event
from .cycle import canon_type

VALID_TYPES = {"cycle", "lab", "symptom", "sleep", "med"}
# legacy short codes used in prototype/tests
ALIASES = {"cyc": "cycle", "sym": "symptom", "slp": "sleep"}


class ImportResult(BaseModel):
    added: int = 0
    skipped: int = 0
    errors: list[str] = []


def _norm_type(t: str) -> Optional[str]:
    t = (t or "").strip().lower()
    if t in VALID_TYPES:
        return t
    return ALIASES.get(t)


def _base_id(ev_type: str, d: Date, code: Optional[str]) -> str:
    prefix = {"cycle": "CYC", "lab": "LAB", "symptom": "SYM", "sleep": "SLP", "med": "MED"}[ev_type]
    mmdd = f"{d.month:02d}{d.day:02d}"
    if ev_type in ("lab", "symptom") and code:
        return f"{prefix}-{mmdd}-{code}"
    return f"{prefix}-{mmdd}"


def _gen_id(ev_type: str, d: Date, code: Optional[str], name: str, existing: set[str]) -> str:
    base = _base_id(ev_type, d, code)
    cand = base
    i = 2
    while cand in existing:
        cand = f"{base}-{i}"
        i += 1
    existing.add(cand)
    return cand


def import_rows(
    rows: list[dict], patient_id: str, source: str, source_ref: str
) -> ImportResult:
    db = SessionLocal()
    try:
        db_ids = {r[0] for r in db.query(Event.id).filter(Event.patient_id == patient_id).all()}
        existing = set(db_ids)
        # content fingerprint for idempotency: same date/type/name/code/value/severity => skip
        seen_content = set()
        for r in db.query(Event).filter(Event.patient_id == patient_id).all():
            seen_content.add((str(r.date), canon_type(r.type), r.name, str(r.code), str(r.value), str(r.severity)))
        res = ImportResult()
        for idx, row in enumerate(rows, start=1):
            try:
                raw_date = str(row.get("date", "")).strip()
                d = Date.fromisoformat(raw_date)
            except Exception:
                res.errors.append(f"row {idx}: bad date {row.get('date')!r}")
                continue
            ev_type = _norm_type(str(row.get("type", "")))
            if not ev_type:
                res.errors.append(f"row {idx}: unknown type {row.get('type')!r}")
                continue
            if d > settings.today_date:
                res.errors.append(f"row {idx}: date {raw_date} is in the future")
                continue
            name = str(row.get("name", "") or "").strip() or ev_type
            code = str(row.get("code", "") or "").strip() or None
            unit = str(row.get("unit", "") or "").strip() or None
            note = str(row.get("note", "") or "")
            if len(name) > 80 or (code and len(code) > 10) or (unit and len(unit) > 20) or len(note) > 2000:
                res.errors.append(f"row {idx}: a field is too long (name 80, code 10, unit 20, note 2000 characters)")
                continue
            value = row.get("value")
            severity = row.get("severity")
            try:
                fval = float(value) if value not in (None, "") else None
            except Exception:
                res.errors.append(f"row {idx}: bad value {value!r}")
                continue
            if ev_type == "lab" and fval is None:
                res.errors.append(f"row {idx}: lab requires numeric value")
                continue
            try:
                sev = int(severity) if severity not in (None, "") else None
            except Exception:
                res.errors.append(f"row {idx}: bad severity {severity!r}")
                continue
            if sev is not None and not (1 <= sev <= 10):
                res.errors.append(f"row {idx}: severity out of range 1-10")
                continue
            if ev_type == "symptom" and sev is None:
                res.errors.append(f"row {idx}: symptom requires severity 1-10")
                continue
            fingerprint = (str(d), ev_type, name, str(code), str(fval), str(sev))
            if fingerprint in seen_content:
                res.skipped += 1
                continue
            eid = _gen_id(ev_type, d, code, name, existing)
            seen_content.add(fingerprint)
            db.add(
                Event(
                    id=eid,
                    patient_id=patient_id,
                    date=d,
                    type=ev_type,
                    name=name,
                    code=code,
                    value=fval,
                    unit=unit,
                    severity=sev,
                    note=note,
                    source=source,
                    source_ref=source_ref,
                )
            )
            res.added += 1
        db.commit()
        return res
    finally:
        db.close()
