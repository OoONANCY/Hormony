from __future__ import annotations

import csv
import io
import json
import math

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import get_db
from ..ledger import cycle as cyc
from ..ledger.importer import import_rows
from ..ledger.profiles import cycle_length_for, today_for
from ..ledger.store import event_out
from ..models import Event, User
from ..schemas import EventIn, EventOut, SummaryOut, TimelineOut

router = APIRouter()

TYPES = {"cycle", "lab", "symptom", "sleep", "med"}
PREFIX = {"cycle": "CYC", "lab": "LAB", "symptom": "SYM", "sleep": "SLP", "med": "MED"}
def _require_patient(pid: str, user_id: str, db: Session) -> None:
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if user.patient_id != pid:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this patient",
        )


def _rows(db: Session, pid: str):
    return db.query(Event).filter(Event.patient_id == pid).order_by(Event.date.asc(), Event.id.asc()).all()


@router.get("/patients/{pid}/timeline", response_model=TimelineOut)
def timeline(
    pid: str,
    days: int = Query(91, ge=1, le=3660),
    types: str = "",
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_patient(pid, current_user, db)
    today = today_for(pid)
    rows = _rows(db, pid)
    starts = cyc.period_starts(rows)
    wanted = {cyc.canon_type(t.strip().lower()) for t in types.split(",") if t.strip()}
    unknown = wanted - TYPES
    if unknown:
        raise HTTPException(400, f"unknown type(s): {', '.join(sorted(unknown))}; use {', '.join(sorted(TYPES))}")
    lo = today.fromordinal(today.toordinal() - (days - 1))
    n = cycle_length_for(pid)
    events = [event_out(r, starts, n) for r in rows
              if lo <= r.date <= today and (not wanted or cyc.canon_type(r.type) in wanted)]
    return TimelineOut(events=events, cycle_starts=starts, today=today)


@router.get("/patients/{pid}/summary", response_model=SummaryOut)
def summary(
    pid: str,
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
    ):
    _require_patient(pid, current_user, db)
    rows = _rows(db, pid)
    counts = {k: 0 for k in sorted(TYPES)}
    for r in rows:
        counts[cyc.canon_type(r.type)] = counts.get(cyc.canon_type(r.type), 0) + 1
    return SummaryOut(counts=counts, days_tracked=len({r.date for r in rows}))


@router.post("/patients/{pid}/events", response_model=EventOut)
def create_event(
    pid: str,
    body: EventIn,
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_patient(pid, current_user, db)
    t = cyc.canon_type((body.type or "").strip().lower())
    if t not in TYPES:
        raise HTTPException(400, f"unknown type {body.type!r}")
    today = today_for(pid)
    d = body.date or today
    if d > today:
        raise HTTPException(400, "date cannot be in the future")
    if body.value is not None and not math.isfinite(body.value):
        raise HTTPException(400, "value must be a finite number")
    if t == "lab" and body.value is None:
        raise HTTPException(400, "lab requires numeric value")
    if t == "sleep" and (body.value is None or not 0 <= body.value <= 24):
        raise HTTPException(400, "sleep requires hours between 0 and 24")
    if t == "symptom" and (body.severity is None or not 1 <= body.severity <= 10):
        raise HTTPException(400, "symptom requires severity 1-10")
    code = (body.code or "").strip() or None
    base = f"{PREFIX[t]}-{d.month:02d}{d.day:02d}" + (f"-{code}" if t in ("lab", "symptom") and code else "")
    existing = {r[0] for r in db.query(Event.id).filter(Event.patient_id == pid).all()}
    cand, i = base, 2
    while cand in existing:
        cand, i = f"{base}-{i}", i + 1
    e = Event(id=cand, patient_id=pid, date=d, type=t, name=body.name or t, code=code, value=body.value,
              unit=body.unit, severity=body.severity, note=body.note or "",
              source=body.source or ("Daily check-in" if t in ("symptom", "sleep") else "Manual entry"),
              source_ref=body.source_ref)
    db.add(e)
    db.commit()
    db.refresh(e)
    return event_out(e, cyc.period_starts(_rows(db, pid)), cycle_length_for(pid))


@router.post("/patients/{pid}/import")
async def import_file(
    pid: str,
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_patient(pid, current_user, db)
    raw = await file.read()
    name = (file.filename or "").lower()
    try:
        text = raw.decode("utf-8-sig")
        if name.endswith(".json"):
            rows = json.loads(text)
            if isinstance(rows, dict):
                rows = rows.get("events", rows.get("rows"))
        else:
            rows = list(csv.DictReader(io.StringIO(text)))
    except (UnicodeDecodeError, json.JSONDecodeError, csv.Error) as ex:
        raise HTTPException(400, f"cannot parse file: {ex}")
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise HTTPException(400, "expected a list of event objects (or {\"events\": [...]})")
    res = import_rows(rows, pid, source=f"Imported {file.filename}", source_ref=file.filename)
    return res.model_dump()
