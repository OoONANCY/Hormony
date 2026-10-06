"""Profiles: a demo profile with a frozen date, personal profiles that start empty on the real date."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from hormony.api.main import create_app
from hormony.ledger import profiles

REAL_TODAY = date(2026, 10, 6)


@pytest.fixture()
def client(seeded, monkeypatch):
    monkeypatch.setattr(profiles, "real_today", lambda: REAL_TODAY)
    with TestClient(create_app(), raise_server_exceptions=False) as c:
        yield c


def _create(c, **kw):
    body = {"name": "Aditi", "last_period_start": "2026-09-20", "cycle_length": 30, **kw}
    return c.post("/profiles", json=body)


def test_seed_creates_the_demo_profile(client):
    demo = next(p for p in client.get("/profiles").json() if p["id"] == "nancy")
    assert (demo["name"], demo["kind"], demo["today"]) == ("Nancy", "demo", "2026-09-29")
    assert demo["counts"]["lab"] == 10


def test_onboarding_creates_an_empty_personal_profile(client):
    r = _create(client)
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["kind"] == "personal" and p["name"] == "Aditi" and p["cycle_length"] == 30
    assert p["today"] == "2026-10-06"
    tl = client.get(f"/patients/{p['id']}/timeline").json()
    assert tl["today"] == "2026-10-06"
    assert tl["cycle_starts"] == ["2026-09-20"]
    assert [(e["type"], e["name"], e["source"]) for e in tl["events"]] == [("cycle", "Period started", "Onboarding")]
    assert tl["events"][0]["cycle_day"] == 1
    assert p["id"] in [x["id"] for x in client.get("/profiles").json()]


def test_personal_profiles_use_the_real_date_for_new_records(client):
    pid = _create(client).json()["id"]
    r = client.post(f"/patients/{pid}/events", json={"type": "symptom", "name": "Fatigue", "severity": 5})
    assert r.json()["date"] == "2026-10-06" and r.json()["cycle_day"] == 17
    assert client.post(f"/patients/{pid}/events",
                       json={"type": "symptom", "name": "Fatigue", "severity": 5, "date": "2026-10-07"}).status_code == 400


def test_onboarding_validation(client):
    assert _create(client, name="").status_code == 422
    assert _create(client, cycle_length=12).status_code == 422
    assert _create(client, last_period_start="2026-10-20").status_code == 400      # future
    assert _create(client, last_period_start="2026-01-01").status_code == 400      # too long ago to anchor a cycle


def test_deleting_a_personal_profile_removes_all_of_its_data(client):
    pid = _create(client).json()["id"]
    client.post(f"/patients/{pid}/events", json={"type": "symptom", "name": "Fatigue", "severity": 5})
    assert client.delete(f"/profiles/{pid}").status_code == 204
    assert pid not in [x["id"] for x in client.get("/profiles").json()]
    assert client.get(f"/patients/{pid}/timeline").json()["events"] == []
    assert client.delete("/profiles/nancy").status_code == 400                     # the demo can't be deleted
    assert client.get("/profiles/nope").status_code == 404


def test_analysis_runs_on_a_personal_profile(client):
    pid = _create(client).json()["id"]
    run_id = client.post("/analyses", json={"patient_id": pid, "question": "What patterns are there?"}).json()["id"]
    with client.stream("GET", f"/analyses/{run_id}/stream") as r:
        events = [line for line in r.iter_lines() if line.startswith("data: ")]
    assert '"type": "done"' in events[-1]
    full = client.get(f"/analyses/{run_id}").json()
    assert full["stats"]["today"] == "2026-10-06"
    for h in (full["hypotheses"] or {}).values():
        assert not [i for i in (h or {}).get("evidence_ids", []) if i.startswith(("LAB-", "SYM-", "MED-"))]


def test_existing_demo_ledgers_get_their_profile_at_startup(seeded):
    """Databases created before profiles existed still have Nancy's records but no profile row."""
    from hormony.db import SessionLocal, init_db
    from hormony.models import Profile
    db = SessionLocal()
    try:
        db.query(Profile).delete()
        db.commit()
    finally:
        db.close()
    init_db()
    p = profiles.get_profile("nancy")
    assert p is not None and p.kind == "demo"


def test_a_long_cycle_moves_the_late_luteal_window(client):
    pid = _create(client, cycle_length=35, last_period_start="2026-09-06").json()["id"]
    for day in ("2026-10-03", "2026-10-04", "2026-09-28"):          # cycle days 28, 29 and 23
        client.post(f"/patients/{pid}/events", json={"type": "symptom", "name": "Fatigue", "severity": 6, "date": day})
    run_id = client.post("/analyses", json={"patient_id": pid, "question": "Is my fatigue cyclical?"}).json()["id"]
    with client.stream("GET", f"/analyses/{run_id}/stream") as r:
        list(r.iter_lines())
    full = client.get(f"/analyses/{run_id}").json()
    assert full["stats"]["late_window"] == [27, 35]
    assert full["stats"]["focus"]["late_n"] == 2
    cyc_facts = [f["statement"] for f in full["facts"]["cycle"]]
    assert "2 of 3 fatigue logs fall on cycle days 27–35" in cyc_facts
    assert all("20–28" not in o["text"] for o in full["brief"]["observations"])
    tl = client.get(f"/patients/{pid}/timeline").json()
    assert {e["date"]: e["phase"] for e in tl["events"]}["2026-09-28"] == "Ovulation"


def test_profiles_keep_their_own_record_ids(client):
    """Record ids are per person: two people who log the same thing on the same day must not collide."""
    a = _create(client, name="Aditi", last_period_start="2026-09-06").json()["id"]
    b = _create(client, name="Bela", last_period_start="2026-09-06")
    assert b.status_code == 201, b.text
    b = b.json()["id"]
    for pid in (a, b, "nancy"):
        r = client.post(f"/patients/{pid}/events", json={"type": "symptom", "name": "Fatigue", "code": "FAT",
                                                          "severity": 5, "date": "2026-09-20"})
        assert r.status_code == 200, r.text
    for pid in (a, b):
        ids = [e["id"] for e in client.get(f"/patients/{pid}/timeline").json()["events"]]
        assert ids == ["CYC-0906", "SYM-0920-FAT"]
    assert client.get("/profiles/nancy").json()["counts"]["symptom"] > 1


def test_old_databases_move_to_per_person_record_ids(tmp_path):
    from sqlalchemy import create_engine, inspect, text
    from hormony.db import migrate_event_keys
    eng = create_engine(f"sqlite:///{tmp_path}/old.db")
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE events (id VARCHAR(40) NOT NULL, patient_id VARCHAR(40) NOT NULL, "
                          "date DATE NOT NULL, type VARCHAR(10) NOT NULL, name VARCHAR(80) NOT NULL, code VARCHAR(10), "
                          "value FLOAT, unit VARCHAR(20), severity INTEGER, note TEXT NOT NULL, "
                          "source VARCHAR(80) NOT NULL, source_ref VARCHAR(200), "
                          "created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, PRIMARY KEY (id))"))
        conn.execute(text("CREATE INDEX ix_events_patient_id ON events (patient_id)"))
        conn.execute(text("INSERT INTO events (id, patient_id, date, type, name, note, source) "
                          "VALUES ('CYC-0906', 'nancy', '2026-09-06', 'cycle', 'Period started', '', 'Seed')"))
    migrate_event_keys(eng)
    migrate_event_keys(eng)  # running it twice is harmless
    assert sorted(inspect(eng).get_pk_constraint("events")["constrained_columns"]) == ["id", "patient_id"]
    with eng.begin() as conn:
        conn.execute(text("INSERT INTO events (id, patient_id, date, type, name, note, source) "
                          "VALUES ('CYC-0906', 'aditi', '2026-09-06', 'cycle', 'Period started', '', 'Onboarding')"))
        rows = conn.execute(text("SELECT patient_id, id, source FROM events ORDER BY patient_id")).all()
    assert [tuple(r) for r in rows] == [("aditi", "CYC-0906", "Onboarding"), ("nancy", "CYC-0906", "Seed")]
    assert "events_old" not in inspect(eng).get_table_names()
