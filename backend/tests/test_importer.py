from hormony.db import SessionLocal
from hormony.ledger.importer import import_rows
from hormony.models import Event


def test_importer_is_idempotent_and_keeps_provenance(seeded):
    rows = [
        {"date": "2026-09-28", "type": "lab", "name": "Ferritin", "code": "FER", "value": "40", "unit": "ng/mL"},
        {"date": "2026-09-28", "type": "symptom", "name": "Fatigue", "code": "F", "severity": "6"},
    ]
    r1 = import_rows(rows, "nancy", source="Imported t.csv", source_ref="t.csv")
    assert (r1.added, r1.skipped) == (2, 0), r1
    r2 = import_rows(rows, "nancy", source="Imported t.csv", source_ref="t.csv")
    assert (r2.added, r2.skipped) == (0, 2), r2
    db = SessionLocal()
    fer = db.query(Event).filter(Event.code == "FER").one()
    db.close()
    assert (fer.source, fer.source_ref, fer.type) == ("Imported t.csv", "t.csv", "lab")


def test_bad_rows_are_reported_and_the_rest_import(seeded):
    bad = [{"date": "2026-09-28", "type": "foo", "name": "X"},
           {"date": "2026-09-28", "type": "lab", "name": "Estradiol", "code": "E2", "value": "120", "unit": "pg/mL"}]
    r = import_rows(bad, "nancy", source="Test", source_ref="t.csv")
    assert r.added == 1 and len(r.errors) == 1 and "row 1" in r.errors[0]


def test_seeded_rows_are_recognised_as_duplicates(seeded):
    # same content as the seeded SYM-0927-F (severity 8)
    r = import_rows([{"date": "2026-09-27", "type": "symptom", "name": "Fatigue", "code": "F", "severity": "8"}],
                    "nancy", source="Test", source_ref="t.csv")
    assert (r.added, r.skipped) == (0, 1)
