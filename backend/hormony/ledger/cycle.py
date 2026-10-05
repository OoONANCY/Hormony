from __future__ import annotations

import re
from datetime import date as Date, timedelta
from statistics import median
from typing import Iterable, List, Optional

LEGACY_TYPES = {"cyc": "cycle", "sym": "symptom", "slp": "sleep"}
_PERIOD_START = re.compile(r"\bperiod\s+(start|started|starts|began)\b", re.I)


def canon_type(t: str) -> str:
    return LEGACY_TYPES.get(t, t)


def is_period_start(name: Optional[str], code: Optional[str] = None) -> bool:
    """Only an actual period start moves the cycle; flow or spotting logs never do."""
    return bool(_PERIOD_START.search(name or "")) or (code or "").upper() == "START"


def period_starts(rows: Iterable) -> List[Date]:
    """Cycle start dates derived from a patient's own cycle events."""
    return sorted({r.date for r in rows if canon_type(r.type) == "cycle" and is_period_start(r.name, r.code)})


def cycle_day(d: Date, starts: List[Date]) -> Optional[int]:
    prior = [s for s in starts if s <= d]
    return (d - max(prior)).days + 1 if prior else None


def phase(cd: int) -> str:
    if cd <= 5:
        return "Period"
    if cd <= 13:
        return "Follicular"
    if cd <= 16:
        return "Ovulation"
    if cd <= 19:
        return "Early luteal"
    return "Late luteal"


def is_late(cd: Optional[int]) -> bool:
    return cd is not None and 20 <= cd <= 28


def predict_next_start(starts: List[Date]) -> Date:
    s = sorted(starts)
    gaps = [(b - a).days for a, b in zip(s, s[1:])] or [28]
    return s[-1] + timedelta(days=round(median(gaps)))
