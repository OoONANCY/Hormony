"""Profiles: the demo profile keeps a frozen date; personal profiles start empty and use the real date."""
from __future__ import annotations

import re
import secrets
from datetime import date as Date, timedelta
from typing import List, Optional

from ..config import settings
from ..db import SessionLocal
from ..models import AnalysisRun, Event, Profile

MAX_ANCHOR_DAYS = 120   # a last-period date older than this can't anchor the current cycle


def real_today() -> Date:
    return Date.today()


def get_profile(pid: str) -> Optional[Profile]:
    db = SessionLocal()
    try:
        return db.query(Profile).filter(Profile.id == pid).first()
    finally:
        db.close()


def today_for(pid: str) -> Date:
    """Personal profiles live in real time; the demo (and any unknown patient) uses HORMONY_TODAY."""
    p = get_profile(pid)
    return real_today() if p is not None and p.kind == "personal" else settings.today_date


def cycle_length_for(pid: str) -> int:
    p = get_profile(pid)
    return p.cycle_length if p is not None and p.cycle_length else 28


def ensure_demo_profile(pid: str = "nancy", name: str = "Nancy") -> None:
    db = SessionLocal()
    try:
        if not db.query(Profile).filter(Profile.id == pid).first():
            db.add(Profile(id=pid, name=name, kind="demo", cycle_length=28))
            db.commit()
    finally:
        db.close()


def list_profiles() -> List[Profile]:
    db = SessionLocal()
    try:
        return db.query(Profile).order_by(Profile.kind.asc(), Profile.created_at.asc()).all()
    finally:
        db.close()


def create_profile(name: str, last_period_start: Date, cycle_length: int) -> Profile:
    today = real_today()
    if last_period_start > today:
        raise ValueError("last period start can't be in the future")
    if last_period_start < today - timedelta(days=MAX_ANCHOR_DAYS):
        raise ValueError(f"last period start must be within the last {MAX_ANCHOR_DAYS} days")
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:20] or "me"
    db = SessionLocal()
    try:
        pid = f"{slug}-{secrets.token_hex(2)}"
        while db.query(Profile).filter(Profile.id == pid).first():
            pid = f"{slug}-{secrets.token_hex(2)}"
        profile = Profile(id=pid, name=name.strip(), kind="personal", cycle_length=cycle_length)
        db.add(profile)
        d = last_period_start
        db.add(Event(id=f"CYC-{d.month:02d}{d.day:02d}", patient_id=pid, date=d, type="cycle", name="Period started",
                     note="", source="Onboarding"))
        db.commit()
        db.refresh(profile)
        return profile
    finally:
        db.close()


def delete_profile(pid: str) -> None:
    """Remove a personal profile and everything that belongs to it (records and analyses)."""
    db = SessionLocal()
    try:
        p = db.query(Profile).filter(Profile.id == pid).first()
        if p is None:
            raise LookupError(pid)
        if p.kind != "personal":
            raise ValueError("the demo profile can't be deleted")
        for model in (Event, AnalysisRun):
            db.query(model).filter(model.patient_id == pid).delete()
        db.delete(p)
        db.commit()
    finally:
        db.close()
