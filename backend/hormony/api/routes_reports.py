"""Lab reports: upload -> extracted rows for review -> confirmed rows saved with provenance to the stored file."""
from __future__ import annotations

import hashlib
import math
import os
from datetime import date as Date
from typing import List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..agents.llm import AgentUnavailable, LLMConfigError, resolve_llm, resolve_vision_llm
from ..config import settings
from ..db import SessionLocal
from ..ledger.profiles import today_for
from ..models import Event, ReportFile
from ..reports.extract import NeedsVision, ReportExtraction, UnsupportedFile, kind_of, read_report, review_rows

router = APIRouter()
MAX_BYTES = 15 * 1024 * 1024
EXT = {"pdf": ".pdf", "image": ".img"}


def text_llm():
    return resolve_llm(settings)


def vision_llm():
    return resolve_vision_llm(settings)


def _preview(rf: ReportFile, today: Date, duplicate: bool) -> dict:
    extraction = ReportExtraction(**(rf.extraction or {}))
    rows, collected, warnings = review_rows(extraction, today)
    return {"report_id": rf.id, "filename": rf.filename, "method": rf.method, "pages": rf.pages,
            "collected_date": collected, "lab_name": extraction.lab_name, "rows": rows,
            "warnings": list((rf.extraction or {}).get("_warnings", [])) + warnings, "duplicate": duplicate}


@router.post("/patients/{pid}/reports")
async def upload_report(pid: str, file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "file is larger than 15 MB")
    try:
        kind = kind_of(file.filename or "", file.content_type or "")
    except UnsupportedFile as e:
        raise HTTPException(415, str(e))
    digest = hashlib.sha256(data).hexdigest()
    today = today_for(pid)
    db = SessionLocal()
    try:
        existing = db.query(ReportFile).filter(ReportFile.id == digest, ReportFile.patient_id == pid).first()
        if existing is not None:  # same file again: reuse the earlier reading instead of calling the model again
            return _preview(existing, today, duplicate=True)
    finally:
        db.close()
    try:
        extraction, method, pages, warnings = await read_report(data, file.filename or "", file.content_type or "",
                                                               text_llm(), vision_llm())
    except NeedsVision as e:
        raise HTTPException(422, str(e))
    except UnsupportedFile as e:
        raise HTTPException(415, str(e))
    except LLMConfigError as e:
        raise HTTPException(503, f"LLM misconfigured: {e}")
    except AgentUnavailable as e:
        raise HTTPException(503, f"The report reader is busy right now ({e}). Try again in a minute.")
    rel = os.path.join(pid, digest + (EXT[kind] if kind == "pdf" else os.path.splitext(file.filename or "")[1].lower() or ".img"))
    os.makedirs(os.path.join(settings.uploads_dir, pid), exist_ok=True)
    with open(os.path.join(settings.uploads_dir, rel), "wb") as f:
        f.write(data)
    db = SessionLocal()
    try:
        rf = ReportFile(id=digest, patient_id=pid, filename=(file.filename or "report")[:200],
                        content_type=(file.content_type or "application/octet-stream")[:80], path=rel, pages=pages,
                        method=method, extraction={**extraction.model_dump(), "_warnings": warnings})
        db.add(rf)
        db.commit()
        db.refresh(rf)
        return _preview(rf, today, duplicate=False)
    finally:
        db.close()


class ConfirmRow(BaseModel):
    analyte: str = Field(min_length=1, max_length=80)
    code: Optional[str] = Field(None, max_length=10)
    value: float
    unit: str = Field("", max_length=20)
    date: str = ""
    reference_range: str = Field("", max_length=40)
    flag: str = Field("", max_length=2)
    page: int = 1


class ConfirmIn(BaseModel):
    rows: List[ConfirmRow]


@router.post("/patients/{pid}/reports/{report_id}/confirm")
def confirm_report(pid: str, report_id: str, body: ConfirmIn):
    today = today_for(pid)
    db = SessionLocal()
    try:
        rf = db.query(ReportFile).filter(ReportFile.id == report_id, ReportFile.patient_id == pid).first()
        if rf is None:
            raise HTTPException(404, "unknown report")
        parsed = []
        for r in body.rows:
            try:
                d = Date.fromisoformat(r.date)
            except ValueError:
                raise HTTPException(400, f"{r.analyte}: set a valid collection date (YYYY-MM-DD)")
            if d > today:
                raise HTTPException(400, f"{r.analyte}: the date {r.date} is in the future")
            if not math.isfinite(r.value):
                raise HTTPException(400, f"{r.analyte}: value must be a number")
            parsed.append((r, d))
        existing = db.query(Event).filter(Event.patient_id == pid).all()
        ids = {e.id for e in existing}
        content = {(e.date, (e.code or e.name).upper(), e.value) for e in existing if e.type == "lab"}
        added, skipped, new_ids = 0, 0, []
        for r, d in parsed:
            key = (d, (r.code or r.analyte).upper(), r.value)
            if key in content:
                skipped += 1
                continue
            base = f"LAB-{d.month:02d}{d.day:02d}-{(r.code or r.analyte[:6]).upper().replace(' ', '')}"
            eid, i = base, 2
            while eid in ids:
                eid, i = f"{base}-{i}", i + 1
            note = " · ".join(x for x in (f"Reference range {r.reference_range}" if r.reference_range else "",
                                          f"Flagged {r.flag}" if r.flag else "") if x)
            db.add(Event(id=eid, patient_id=pid, date=d, type="lab", name=r.analyte, code=r.code, value=r.value,
                         unit=r.unit or None, note=note, source=f"Lab report: {rf.filename}"[:80],
                         source_ref=f"report:{rf.id}#p{r.page}"))
            ids.add(eid)
            content.add(key)
            new_ids.append(eid)
            added += 1
        db.commit()
        return {"added": added, "skipped": skipped, "ids": new_ids}
    finally:
        db.close()


@router.get("/patients/{pid}/reports/{report_id}/file")
def report_file(pid: str, report_id: str):
    db = SessionLocal()
    try:
        rf = db.query(ReportFile).filter(ReportFile.id == report_id, ReportFile.patient_id == pid).first()
    finally:
        db.close()
    path = os.path.join(settings.uploads_dir, rf.path) if rf else ""
    if rf is None or not os.path.exists(path):
        raise HTTPException(404, "unknown report")
    return FileResponse(path, media_type=rf.content_type, filename=rf.filename)
