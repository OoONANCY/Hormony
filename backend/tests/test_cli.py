from hormony import cli
from hormony.db import SessionLocal
from hormony.models import AnalysisRun, Event
from tests.conftest import add_event


def _count(pid="nancy"):
    db = SessionLocal()
    try:
        return db.query(Event).filter(Event.patient_id == pid).count()
    finally:
        db.close()


def _latest_run():
    db = SessionLocal()
    try:
        return db.query(AnalysisRun).order_by(AnalysisRun.created_at.desc()).first()
    finally:
        db.close()


def test_cli_keeps_existing_data_and_saves_a_complete_run(seeded):
    add_event(id="LAB-0928-FER", date="2026-09-28", type="lab", name="Ferritin", code="FER", value=18, unit="ng/mL")
    cli.main(["ask", "Why fatigue?", "--demo"])
    assert _count() == 131
    run = _latest_run()
    assert run.status == "done"
    assert {"report", "graph", "brief", "facts"} <= set(run.result)
    assert run.event_log[-1]["type"] == "done"


def test_cli_seeds_only_an_empty_ledger(seeded):
    db = SessionLocal()
    db.query(Event).delete()
    db.commit()
    db.close()
    cli.main(["ask", "q", "--demo"])
    assert _count() == 130
