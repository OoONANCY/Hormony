"""Read access to a patient's evidence ledger, with cycle context computed from their own data."""
from __future__ import annotations

from datetime import date as Date
from typing import List, Tuple

from ..db import SessionLocal
from ..models import Event
from ..schemas import EventOut
from . import cycle as cyc
from .profiles import cycle_length_for, today_for


def event_out(row: Event, starts: List[Date], cycle_length: int = 28) -> EventOut:
    cd = cyc.cycle_day(row.date, starts)
    return EventOut(
        id=row.id, date=row.date, type=cyc.canon_type(row.type), name=row.name, code=row.code,
        value=row.value, unit=row.unit, severity=row.severity, note=row.note or "",
        source=row.source or "", source_ref=row.source_ref,
        cycle_day=cd, phase=cyc.phase(cd, cycle_length) if cd else None,
    )


def load_ledger(patient_id: str) -> Tuple[List[EventOut], List[Date], Date]:
    """All events for one patient, their period-start dates, and that profile's 'today'."""
    db = SessionLocal()
    try:
        rows = (db.query(Event).filter(Event.patient_id == patient_id)
                .order_by(Event.date.asc(), Event.id.asc()).all())
        starts = cyc.period_starts(rows)
        n = cycle_length_for(patient_id)
        return [event_out(r, starts, n) for r in rows], starts, today_for(patient_id)
    finally:
        db.close()
