"""HTTP API: timeline window, validation, import, health, CORS on errors, analyses + SSE, replay."""
import json
import os

import pytest
from fastapi.testclient import TestClient

from hormony.api.main import create_app
from hormony.config import settings
from tests.conftest import add_event

SAMPLE_CSV = os.path.join(os.path.dirname(__file__), "..", "sample_data", "labs.csv")


@pytest.fixture()
def client(seeded):
    with TestClient(create_app(), raise_server_exceptions=False) as c:
        yield c


def _sse(c, run_id):
    events = []
    with c.stream("GET", f"/analyses/{run_id}/stream") as r:
        for line in r.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events


def test_timeline_default_is_the_full_91_day_window(client):
    js = client.get("/patients/nancy/timeline").json()
    assert len(js["events"]) == 129                        # Jul 1 – Sep 29; the Jun 14 start is outside
    assert js["cycle_starts"] == ["2026-06-14", "2026-07-12", "2026-08-09", "2026-09-06"]
    lab = next(e for e in js["events"] if e["id"] == "LAB-0926-P4")
    assert (lab["cycle_day"], lab["phase"]) == (21, "Late luteal")


def test_timeline_rejects_bad_parameters(client):
    assert client.get("/patients/nancy/timeline", params={"days": 0}).status_code == 422
    assert client.get("/patients/nancy/timeline", params={"types": "foo"}).status_code == 400
    assert len(client.get("/patients/nancy/timeline", params={"types": "lab"}).json()["events"]) == 10


def test_only_period_starts_move_the_cycle(client):
    r = client.post("/patients/nancy/events", json={"type": "cycle", "name": "Spotting", "date": "2026-09-29"})
    assert r.status_code == 200, r.text
    assert r.json()["cycle_day"] == 24
    assert "2026-09-29" not in client.get("/patients/nancy/timeline").json()["cycle_starts"]


def test_cycle_starts_come_from_each_patients_own_data(client):
    add_event(id="CYC-0910", patient_id="bob", date="2026-09-10", type="cycle", name="Period started")
    assert client.get("/patients/bob/timeline").json()["cycle_starts"] == ["2026-09-10"]


def test_event_validation(client):
    post = lambda body: client.post("/patients/nancy/events", json=body)  # noqa: E731
    assert post({"type": "sleep", "name": "Sleep", "value": -3, "unit": "h"}).status_code == 400
    assert post({"type": "sleep", "name": "Sleep", "value": 7, "unit": "h", "date": "2026-10-30"}).status_code == 400
    assert post({"type": "med", "name": "x" * 200}).status_code == 422
    ok = post({"type": "symptom", "name": "Fatigue", "severity": 6, "code": "F"})
    assert ok.status_code == 200, ok.text
    ids = [e["id"] for e in client.get("/patients/nancy/timeline").json()["events"]]
    assert ok.json()["id"] in ids


def test_import_rejects_malformed_json(client):
    for payload in ({"events": 5}, [1, 2]):
        r = client.post("/patients/nancy/import", files={"file": ("x.json", json.dumps(payload), "application/json")})
        assert r.status_code == 400, (payload, r.status_code, r.text)


def test_import_dedupes_against_the_seed_and_is_idempotent(client):
    with open(SAMPLE_CSV, "rb") as f:
        data = f.read()
    first = client.post("/patients/nancy/import", files={"file": ("labs.csv", data, "text/csv")}).json()
    again = client.post("/patients/nancy/import", files={"file": ("labs.csv", data, "text/csv")}).json()
    assert again["added"] == 0 and again["skipped"] == first["added"] + first["skipped"]
    fatigue = [e for e in client.get("/patients/nancy/timeline").json()["events"] if e["name"] == "Fatigue"]
    assert len(fatigue) == 16


def test_health_reports_db_and_llm(client):
    assert client.get("/health").json() == {"ok": True, "db": "ok", "llm": "demo"}


def test_server_errors_still_carry_cors_headers(seeded):
    app = create_app()

    @app.get("/boom")
    def boom():
        raise RuntimeError("boom")
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/boom", headers={"Origin": "http://phone"})
    assert r.status_code == 500
    assert r.headers.get("access-control-allow-origin") == "*"


def test_misconfigured_llm_is_a_clear_503(client, monkeypatch):
    monkeypatch.setattr(settings, "llm", "openrouter")
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    r = client.post("/analyses", json={"question": "q"})
    assert r.status_code == 503
    assert "OPENROUTER_API_KEY" in r.json()["detail"]


def test_analysis_end_to_end_over_http(client):
    run_id = client.post("/analyses", json={"question": "Why have my fatigue episodes increased?"}).json()["id"]
    events = _sse(client, run_id)
    assert events[0] == {"type": "step", "index": 0, "label": "Scoping your evidence ledger", "llm": "demo"}
    assert events[-1] == {"type": "done", "analysis_id": run_id}
    full = client.get(f"/analyses/{run_id}").json()
    assert full["report"]["headline"] and full["graph"]["edges"] and full["brief"]["observations"]
    assert _sse(client, run_id) == events                     # reconnect replays the same log
    assert client.get("/analyses/nope").status_code == 404


def test_replay_mode_respects_paused_agents(client, monkeypatch):
    monkeypatch.setattr(settings, "demo_replay", True)
    run_id = client.post("/analyses", json={"question": "q", "active_agents": ["symptom", "cycle"]}).json()["id"]
    events = _sse(client, run_id)
    assert {"type": "agent_skipped", "agent": "lab", "reason": "paused"} in events
    assert not [e for e in events if e.get("agent") == "lab" and e["type"] in ("thought", "hypothesis", "message")]
    assert events[-1]["type"] == "done"


def test_golden_run_ships_a_complete_event_log():
    path = os.path.join(os.path.dirname(__file__), "..", "sample_data", "golden_run.json")
    golden = json.load(open(path))
    assert golden["event_log"][-1]["type"] == "done"
    assert {"report", "graph", "brief"} <= set(golden["result"])
