from __future__ import annotations

from datetime import date as Date

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from ..db import SessionLocal
from ..ledger import profiles
from ..ledger.cycle import canon_type
from ..models import Event

router = APIRouter()


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    last_period_start: Date
    cycle_length: int = Field(28, ge=21, le=45)


def _out(p) -> dict:
    db = SessionLocal()
    try:
        counts = {k: 0 for k in ("cycle", "lab", "symptom", "sleep", "med")}
        for (t,) in db.query(Event.type).filter(Event.patient_id == p.id).all():
            counts[canon_type(t)] = counts.get(canon_type(t), 0) + 1
    finally:
        db.close()
    return {"id": p.id, "name": p.name, "kind": p.kind, "cycle_length": p.cycle_length,
            "today": profiles.today_for(p.id).isoformat(), "counts": counts}


@router.get("/profiles")
def list_profiles():
    return [_out(p) for p in profiles.list_profiles()]


@router.post("/profiles", status_code=201)
def create_profile(body: ProfileIn):
    if not body.name.strip():
        raise HTTPException(422, "name is required")
    try:
        return _out(profiles.create_profile(body.name, body.last_period_start, body.cycle_length))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/profiles/{pid}")
def get_profile(pid: str):
    p = profiles.get_profile(pid)
    if p is None:
        raise HTTPException(404, "unknown profile")
    return _out(p)


@router.delete("/profiles/{pid}", status_code=204)
def delete_profile(pid: str):
    try:
        profiles.delete_profile(pid)
    except LookupError:
        raise HTTPException(404, "unknown profile")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return Response(status_code=204)
