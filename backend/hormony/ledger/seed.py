"""91-day demo dataset ported exactly from the hormony-app.html prototype (canonical event types)."""
from __future__ import annotations

from datetime import date, timedelta

from ..db import SessionLocal, init_db
from ..models import Event

DAY0 = date(2026, 7, 1)
TODAY = date(2026, 9, 29)
MED_DAY_IDX = 46  # Aug 16
STARTS_IDX = [-17, 11, 39, 67]  # Jun14, Jul12, Aug9, Sep6
PATIENT = "nancy"


def _to_int32(n: int) -> int:
    n &= 0xFFFFFFFF
    return n - 0x100000000 if n >= 0x80000000 else n


def _to_uint32(n: int) -> int:
    return n & 0xFFFFFFFF


def _imul(a: int, b: int) -> int:
    return _to_int32(_to_uint32(a) * _to_uint32(b))


def _rng(seed: int):
    s = _to_int32(seed)

    def nxt() -> float:
        nonlocal s
        s = _to_int32(s + 0x6D2B79F5)
        t = _imul(s ^ (_to_uint32(s) >> 15), 1 | s)
        t = _to_int32(_to_int32(t + _imul(t ^ (_to_uint32(t) >> 7), 61 | t)) ^ t)
        return (_to_uint32(t ^ (_to_uint32(t) >> 14))) / 4294967296

    return nxt


def _date_of(idx: int) -> date:
    return DAY0 + timedelta(days=idx)


def _md(idx: int) -> str:
    d = _date_of(idx)
    return f"{d.month:02d}{d.day:02d}"


def _cyc_idx(d: int) -> int:
    k = 0
    for i, s in enumerate(STARTS_IDX):
        if d >= s:
            k = i
    return k


def _cd(idx: int) -> int:
    return idx - STARTS_IDX[_cyc_idx(idx)] + 1


def _is_late(cd: int) -> bool:
    return 20 <= cd <= 28


NOTES = {
    "SYM-0928-F": '"Needed a nap by 3pm, even after coffee."',
    "SYM-0819-F": '"Wiped out today. Three days into the new medication."',
    "SYM-0901-F": '"Heavy legs, foggy all afternoon."',
    "SYM-0927-A": '"Restless and on edge before bed."',
}


def build_events() -> list[dict]:
    out: list[dict] = []
    for s in STARTS_IDX:  # includes Jun 14, the start of the cycle that is underway on day 0
        out.append(
            {
                "id": f"CYC-{_md(s)}",
                "date": _date_of(s),
                "type": "cycle",
                "name": "Period started",
                "code": None,
                "value": None,
                "unit": None,
                "severity": None,
                "note": "",
                "source": "Cycle log",
                "source_ref": None,
            }
        )
    labs = [
        (7, "Estradiol", "E2", 88, "pg/mL"),
        (7, "Progesterone", "P4", 6.1, "ng/mL"),
        (7, "TSH", "TSH", 2.6, "mIU/L"),
        (31, "Estradiol", "E2", 132, "pg/mL"),
        (31, "Progesterone", "P4", 7.9, "ng/mL"),
        (63, "Estradiol", "E2", 95, "pg/mL"),
        (63, "Progesterone", "P4", 5.0, "ng/mL"),
        (63, "TSH", "TSH", 2.4, "mIU/L"),
        (87, "Estradiol", "E2", 141, "pg/mL"),
        (87, "Progesterone", "P4", 4.2, "ng/mL"),
    ]
    for d, name, code, v, u in labs:
        out.append(
            {
                "id": f"LAB-{_md(d)}-{code}",
                "date": _date_of(d),
                "type": "lab",
                "name": name,
                "code": code,
                "value": float(v),
                "unit": u,
                "severity": None,
                "note": "",
                "source": "Uploaded lab report (PDF)",
                "source_ref": f"lab_report_{_date_of(d).isoformat()}.pdf",
            }
        )
    symn = {"F": "Fatigue", "A": "Anxiety", "H": "Headache", "B": "Bloating"}
    rows = [
        ("F", [[6, 5], [8, 4], [32, 5], [34, 6], [36, 5], [49, 6], [52, 6], [60, 7], [62, 7], [64, 6], [65, 7], [73, 6], [86, 7], [87, 7], [88, 8], [89, 7]]),
        ("A", [[33, 5], [62, 6], [85, 6], [88, 7]]),
        ("H", [[9, 4], [35, 5], [64, 5], [88, 6]]),
        ("B", [[35, 4], [87, 5]]),
    ]
    for c, lst in rows:
        for d, sev in lst:
            eid = f"SYM-{_md(d)}-{c}"
            out.append(
                {
                    "id": eid,
                    "date": _date_of(d),
                    "type": "symptom",
                    "name": symn[c],
                    "code": c,
                    "value": None,
                    "unit": None,
                    "severity": sev,
                    "note": NOTES.get(eid, ""),
                    "source": "Daily check-in",
                    "source_ref": None,
                }
            )
    out.append(
        {
            "id": "MED-0816",
            "date": _date_of(MED_DAY_IDX),
            "type": "med",
            "name": "Spironolactone 50 mg",
            "code": None,
            "value": None,
            "unit": None,
            "severity": None,
            "note": "Prescribed for hormonal acne.",
            "source": "Manual entry",
            "source_ref": None,
        }
    )
    r = _rng(7)
    for d in range(0, 89):
        base = 6.2 if _is_late(_cd(d + 1)) else 7.3
        if d >= MED_DAY_IDX:
            base -= 0.45
        h = round((base + (r() - 0.5) * 0.9) * 10) / 10
        out.append(
            {
                "id": f"SLP-{_md(d)}",
                "date": _date_of(d),
                "type": "sleep",
                "name": "Sleep",
                "code": None,
                "value": None,
                "unit": None,
                "severity": None,
                "note": "",
                "source": "Sleep app · CSV import",
                "source_ref": None,
                "_h": h,
            }
        )
    # stash sleep hours into note? No — sleep hours are not in a column;
    # we encode them via value? Prototype stores h separately.
    # Map _h -> value=None but we need hours: reuse `value` as hours.
    for e in out:
        if e["type"] == "sleep":
            e["value"] = float(e.pop("_h"))
            e["unit"] = "h"
    return out


def seed_db(patient_id: str = PATIENT) -> int:
    init_db()
    db = SessionLocal()
    try:
        db.query(Event).filter(Event.patient_id == patient_id).delete()
        db.commit()
        events = build_events()
        for e in events:
            db.add(Event(patient_id=patient_id, **e))
        db.commit()
        return len(events)
    finally:
        db.close()


if __name__ == "__main__":
    n = seed_db()
    print(f"seeded {n} events for {PATIENT}")
