"""Test isolation: a throwaway SQLite DB, no real LLM keys, no developer .env.

This runs before any test module imports `hormony`, so `hormony.config.settings` picks these up.
"""
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="hormony-tests-")
os.environ["HORMONY_DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ.pop("HORMONY_DEMO_REPLAY", None)
if not os.environ.get("HORMONY_LIVE_TESTS"):  # live tests keep the developer's real keys / .env
    os.environ["HORMONY_ENV_FILE"] = os.path.join(_TMP, "no.env")  # never read the developer's real .env
    os.environ["HORMONY_LLM"] = "demo"
    for _k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "HORMONY_ANTHROPIC_API_KEY",
               "OPENROUTER_API_KEY", "HORMONY_OPENROUTER_API_KEY"):
        os.environ.pop(_k, None)

import pytest  # noqa: E402


@pytest.fixture()
def seeded():
    """Fresh demo ledger for patient `nancy` (and an empty one for everybody else)."""
    from hormony.db import init_db, SessionLocal
    from hormony.models import Event, AnalysisRun, Profile
    from hormony.ledger.seed import seed_db
    init_db()
    db = SessionLocal()
    try:
        for model in (Event, AnalysisRun, Profile):
            db.query(model).delete()
        db.commit()
    finally:
        db.close()
    seed_db("nancy")
    from hormony import runner
    runner.RUNS.clear()
    return "nancy"


def add_event(**kw):
    """Insert one ledger row directly (test helper)."""
    from hormony.db import SessionLocal
    from hormony.models import Event
    from datetime import date
    base = dict(patient_id="nancy", code=None, value=None, unit=None, severity=None, note="",
                source="Test", source_ref=None)
    base.update(kw)
    if isinstance(base["date"], str):
        base["date"] = date.fromisoformat(base["date"])
    db = SessionLocal()
    try:
        db.add(Event(**base))
        db.commit()
    finally:
        db.close()


def update_event(event_id: str, **kw):
    from hormony.db import SessionLocal
    from hormony.models import Event
    from datetime import date
    db = SessionLocal()
    try:
        e = db.query(Event).filter(Event.id == event_id).one()
        for k, v in kw.items():
            setattr(e, k, date.fromisoformat(v) if k == "date" and isinstance(v, str) else v)
        db.commit()
    finally:
        db.close()
