from hormony.db import SessionLocal
from hormony.ledger.seed import seed_db
from hormony.models import Event


def _rows():
    db = SessionLocal()
    try:
        return db.query(Event).filter(Event.patient_id == "nancy").all()
    finally:
        db.close()


def test_seed_is_canonical_and_idempotent(seeded):
    assert seed_db("nancy") == 130
    rows = _rows()
    assert len(rows) == 130
    assert {r.type for r in rows} == {"cycle", "lab", "symptom", "sleep", "med"}
    by_id = {r.id: r for r in rows}
    assert by_id["CYC-0614"].name == "Period started"       # the prior start is data, not a hard-coded date
    assert abs(by_id["LAB-0926-P4"].value - 4.2) < 1e-9
    assert len([r for r in rows if r.name == "Fatigue"]) == 16
    assert all(r.source_ref for r in rows if r.type == "lab")
