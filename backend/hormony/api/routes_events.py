from __future__ import annotations

import csv
import io
import json
import math
from datetime import date as Date

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from ..db import get_db
from ..ledger import cycle as cyc
from ..ledger.importer import import_rows
from ..ledger.profiles import cycle_length_for, today_for
from ..ledger.store import event_out
from ..models import Event
from ..schemas import (
    EventIn,
    EventOut,
    SummaryOut,
    TimelineOut,
    WearableIn,
    WearableOut,
)

router = APIRouter()

TYPES = {
    "cycle",
    "lab",
    "symptom",
    "sleep",
    "med",
    "wearable",
}
PREFIX = {
    "cycle": "CYC",
    "lab": "LAB",
    "symptom": "SYM",
    "sleep": "SLP",
    "med": "MED",
    "wearable": "WRB",
}


def _rows(db: Session, pid: str):
    return db.query(Event).filter(Event.patient_id == pid).order_by(Event.date.asc(), Event.id.asc()).all()


@router.get("/patients/{pid}/timeline", response_model=TimelineOut)
def timeline(pid: str, days: int = Query(91, ge=1, le=3660), types: str = "", db: Session = Depends(get_db)):
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
def summary(pid: str, db: Session = Depends(get_db)):
    rows = _rows(db, pid)
    counts = {k: 0 for k in sorted(TYPES)}
    for r in rows:
        counts[cyc.canon_type(r.type)] = counts.get(cyc.canon_type(r.type), 0) + 1
    return SummaryOut(counts=counts, days_tracked=len({r.date for r in rows}))


@router.post("/patients/{pid}/events", response_model=EventOut)
def create_event(pid: str, body: EventIn, db: Session = Depends(get_db)):
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
async def import_file(pid: str, file: UploadFile = File(...)):
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

@router.post(
    "/patients/{pid}/wearable",
    response_model=WearableOut,
)
def create_wearable_data(
    pid: str,
    body: WearableIn,
    db: Session = Depends(get_db),
):
    d = body.date or settings.today_date

    if d > settings.today_date:
        raise HTTPException(
            400,
            "date cannot be in the future",
        )

    if all(
        value is None
        for value in (
            body.sleep_hours,
            body.resting_heart_rate,
            body.hrv,
            body.steps,
            body.body_temperature,
        )
    ):
        raise HTTPException(
            400,
            "at least one wearable metric is required",
        )

    source = body.source.strip() or "wearable"

    source_ref = (
        body.source_ref.strip()
        if body.source_ref
        else f"{source}:{d.isoformat()}"
    )


    metrics = [
        (
            "Sleep duration",
            body.sleep_hours,
            "hours",
            "sleep",
        ),
        (
            "Resting heart rate",
            body.resting_heart_rate,
            "bpm",
            "wearable",
        ),
        (
            "HRV",
            body.hrv,
            "ms",
            "wearable",
        ),
        (
            "Steps",
            body.steps,
            "steps",
            "wearable",
        ),
        (
            "Body temperature",
            body.body_temperature,
            "°C",
            "wearable",
        ),
    ]

    for name, value, unit, event_type in metrics:
        if value is None:
            continue

        metric_ref = f"{source_ref}:{name.lower().replace(' ', '_')}"

        event_id = f"WRB-{d.strftime('%m%d')}-{name[:3].upper()}"

        existing_id = db.query(Event.id).filter(
            Event.patient_id == pid,
            Event.source_ref == metric_ref,
        ).first()

        if existing_id:
            continue

        base_id = event_id
        candidate = base_id
        counter = 2

        while db.query(Event.id).filter(
            Event.id == candidate
        ).first():
            candidate = f"{base_id}-{counter}"
            counter += 1

        event = Event(
            id=candidate,
            patient_id=pid,
            date=d,
            type=event_type,
            name=name,
            value=float(value),
            unit=unit,
            note="Imported from wearable health data",
            source=source,
            source_ref=metric_ref,
        )

        db.add(event)

    db.commit()

    return WearableOut(
        date=d,
        sleep_hours=body.sleep_hours,
        resting_heart_rate=body.resting_heart_rate,
        hrv=body.hrv,
        steps=body.steps,
        body_temperature=body.body_temperature,
        source=source,
    )
@router.get(
    "/patients/{pid}/wearable",
    response_model=WearableOut,
)
def get_wearable_data(
    pid: str,
    date: Date | None = None,
    db: Session = Depends(get_db),
):
    target_date = date or settings.today_date

    events = (
        db.query(Event)
        .filter(
            Event.patient_id == pid,
            Event.date == target_date,
            Event.source.in_([
                "wearable",
                "health_connect",
                "healthkit",
            ]),
        )
        .order_by(Event.id.asc())
        .all()
    )

    result = {
        "date": target_date,
        "sleep_hours": None,
        "resting_heart_rate": None,
        "hrv": None,
        "steps": None,
        "body_temperature": None,
        "source": "wearable",
    }

    for event in events:
        if event.name == "Sleep duration":
            result["sleep_hours"] = event.value
        elif event.name == "Resting heart rate":
            result["resting_heart_rate"] = event.value
        elif event.name == "HRV":
            result["hrv"] = event.value
        elif event.name == "Steps":
            result["steps"] = (
                int(event.value)
                if event.value is not None
                else None
            )
        elif event.name == "Body temperature":
            result["body_temperature"] = event.value

        result["source"] = event.source

    return result
