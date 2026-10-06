"""Accounts: sign up / sign in, and every profile, record, analysis and report is visible only to its owner.

The demo profile is shared sample data: anyone signed in may read and analyse it, nobody may change it.
"""
import datetime as dt

import jwt
import pytest
from fastapi.testclient import TestClient

from hormony.api.main import create_app
from hormony.api import routes_reports
from hormony.auth import FAILED_LOGINS
from hormony.config import settings
from hormony.ledger import profiles
from tests.pdfutil import LAB_REPORT, make_pdf

PDF = make_pdf([LAB_REPORT])


@pytest.fixture()
def anon(seeded, monkeypatch):
    """A client that isn't signed in. The demo has no owner, so it is read-only for everyone."""
    monkeypatch.setattr(profiles, "real_today", lambda: dt.date(2026, 10, 6))
    from tests.test_reports import FakeExtractor, LLM_RESULT
    monkeypatch.setattr(routes_reports, "text_llm", lambda: FakeExtractor(result=LLM_RESULT))
    monkeypatch.setattr(routes_reports, "vision_llm", lambda: None)
    with TestClient(create_app(), raise_server_exceptions=False) as c:
        yield c


def _signup(c, email, password="correct horse 1"):
    r = c.post("/auth/register", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def _h(session):
    return {"Authorization": f"Bearer {session['access_token']}"}


def _profile(c, session, name="Aditi"):
    r = c.post("/profiles", json={"name": name, "last_period_start": "2026-09-20"}, headers=_h(session))
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_sign_up_sign_in_and_who_am_i(anon):
    s = _signup(anon, "Aditi@Example.com")
    assert s["token_type"] == "bearer" and s["email"] == "aditi@example.com" and "patient_id" not in s
    assert anon.get("/auth/me", headers=_h(s)).json() == {"user_id": s["user_id"], "email": "aditi@example.com"}
    again = anon.post("/auth/login", json={"email": "ADITI@example.com", "password": "correct horse 1"})
    assert again.status_code == 200 and again.json()["user_id"] == s["user_id"]
    for email, pw in (("aditi@example.com", "wrong password"), ("nobody@example.com", "correct horse 1")):
        r = anon.post("/auth/login", json={"email": email, "password": pw})
        assert r.status_code == 401 and r.json()["detail"] == "Wrong email or password"   # same answer either way
    assert anon.post("/auth/register", json={"email": "aditi@example.com", "password": "another one 2"}).status_code == 409
    assert anon.post("/auth/register", json={"email": "short@example.com", "password": "short"}).status_code == 422
    assert anon.post("/auth/register", json={"email": "not-an-email", "password": "long enough 1"}).status_code == 422


def test_every_data_route_needs_a_sign_in(anon):
    routes = [("get", "/profiles"), ("post", "/profiles"), ("get", "/profiles/nancy"), ("delete", "/profiles/nancy"),
              ("get", "/patients/nancy/timeline"), ("get", "/patients/nancy/summary"),
              ("post", "/patients/nancy/events"), ("post", "/patients/nancy/import"),
              ("post", "/analyses"), ("get", "/analyses/x"), ("get", "/analyses/x/stream"),
              ("post", "/patients/nancy/reports"), ("post", "/patients/nancy/reports/x/confirm"),
              ("get", "/patients/nancy/reports/x/file"), ("post", "/patients/nancy/reports/x/link"), ("get", "/auth/me")]
    for method, path in routes:
        r = getattr(anon, method)(path)
        assert r.status_code == 401, (method, path, r.status_code)
    assert anon.get("/health").status_code == 200


def test_bad_tokens_are_rejected(anon):
    s = _signup(anon, "aditi@example.com")
    now = dt.datetime.now(dt.timezone.utc)
    expired = jwt.encode({"sub": s["user_id"], "typ": "access", "exp": now - dt.timedelta(minutes=1)},
                         settings.auth_secret, algorithm="HS256")
    forged = jwt.encode({"sub": s["user_id"], "typ": "access", "exp": now + dt.timedelta(hours=1)},
                        "change-this-secret-in-env", algorithm="HS256")
    ghost = jwt.encode({"sub": "no-such-user", "typ": "access", "exp": now + dt.timedelta(hours=1)},
                       settings.auth_secret, algorithm="HS256")
    for token in (expired, forged, ghost, "not-a-token"):
        assert anon.get("/profiles", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    r = anon.get("/profiles", headers={"Authorization": f"Bearer {expired}"})
    assert "expired" in r.json()["detail"]


def test_people_only_see_their_own_profiles_and_records(anon):
    a, b = _signup(anon, "aditi@example.com"), _signup(anon, "bela@example.com")
    pa, pb = _profile(anon, a, "Aditi"), _profile(anon, b, "Bela")
    assert {p["id"] for p in anon.get("/profiles", headers=_h(a)).json()} == {"nancy", pa}
    assert {p["id"] for p in anon.get("/profiles", headers=_h(b)).json()} == {"nancy", pb}
    sym = {"type": "symptom", "name": "Fatigue", "severity": 5, "date": "2026-10-01"}
    for method, path, kw in (("get", f"/profiles/{pb}", {}), ("get", f"/patients/{pb}/timeline", {}),
                             ("get", f"/patients/{pb}/summary", {}), ("post", f"/patients/{pb}/events", {"json": sym}),
                             ("delete", f"/profiles/{pb}", {}),
                             ("post", "/analyses", {"json": {"patient_id": pb, "question": "Why?"}})):
        r = getattr(anon, method)(path, headers=_h(a), **kw)
        assert r.status_code == 404, (method, path, r.status_code)       # someone else's record doesn't exist for you
    assert anon.post(f"/patients/{pa}/events", json=sym, headers=_h(a)).status_code == 200
    assert anon.get(f"/profiles/{pb}", headers=_h(b)).status_code == 200    # Bela's profile is untouched
    assert anon.get(f"/profiles/{pa}", headers=_h(a)).json()["counts"]["symptom"] == 1


def test_the_demo_is_shared_and_read_only(anon):
    a = _signup(anon, "aditi@example.com")
    assert anon.get("/patients/nancy/timeline", headers=_h(a)).status_code == 200
    r = anon.post("/patients/nancy/events", json={"type": "symptom", "name": "Fatigue", "severity": 5}, headers=_h(a))
    assert r.status_code == 403 and "read-only" in r.json()["detail"]
    files = {"file": ("labs.csv", b"date,type,name,value\n2026-09-01,lab,TSH,2.0\n", "text/csv")}
    assert anon.post("/patients/nancy/import", files=files, headers=_h(a)).status_code == 403
    assert anon.post("/patients/nancy/reports", files={"file": ("r.pdf", PDF, "application/pdf")}, headers=_h(a)).status_code == 403
    assert anon.delete("/profiles/nancy", headers=_h(a)).status_code == 400
    assert anon.post("/analyses", json={"patient_id": "nancy", "question": "Why?"}, headers=_h(a)).status_code == 200


def test_analyses_belong_to_whoever_ran_them(anon):
    a, b = _signup(anon, "aditi@example.com"), _signup(anon, "bela@example.com")
    for pid in (_profile(anon, a), "nancy"):          # her own record, and the shared demo
        run = anon.post("/analyses", json={"patient_id": pid, "question": "Why?"}, headers=_h(a)).json()["id"]
        with anon.stream("GET", f"/analyses/{run}/stream", headers=_h(a)) as r:
            assert r.status_code == 200
            list(r.iter_lines())
        assert anon.get(f"/analyses/{run}", headers=_h(a)).status_code == 200
        assert anon.get(f"/analyses/{run}", headers=_h(b)).status_code == 404
        assert anon.get(f"/analyses/{run}/stream", headers=_h(b)).status_code == 404


def test_report_files_open_only_for_their_owner(anon):
    a, b = _signup(anon, "aditi@example.com"), _signup(anon, "bela@example.com")
    pa = _profile(anon, a)
    up = anon.post(f"/patients/{pa}/reports", files={"file": ("Oct.pdf", PDF, "application/pdf")}, headers=_h(a))
    assert up.status_code == 200, up.text
    rid = up.json()["report_id"]
    assert anon.post(f"/patients/{pa}/reports/{rid}/confirm", json={"rows": up.json()["rows"][:1]}, headers=_h(b)).status_code == 404
    assert anon.get(f"/patients/{pa}/reports/{rid}/file", headers=_h(a)).content == PDF
    assert anon.get(f"/patients/{pa}/reports/{rid}/file", headers=_h(b)).status_code == 404
    assert anon.post(f"/patients/{pa}/reports/{rid}/link", headers=_h(b)).status_code == 404
    link = anon.post(f"/patients/{pa}/reports/{rid}/link", headers=_h(a)).json()["url"]
    opened = anon.get(link)                                    # a phone browser opens it without the sign-in header
    assert opened.status_code == 200 and opened.content == PDF
    assert opened.headers["content-disposition"].startswith("inline")
    token = link.rsplit("/", 1)[1]
    assert anon.get("/profiles", headers={"Authorization": f"Bearer {token}"}).status_code == 401   # not a sign-in
    assert anon.get(link[:-3] + "abc").status_code == 404                                         # tampered


def test_the_first_account_adopts_profiles_made_before_accounts(anon):
    early = profiles.create_profile("Me", dt.date(2026, 9, 20), 28).id       # made on a server without accounts
    first, second = _signup(anon, "owner@example.com"), _signup(anon, "guest@example.com")
    assert early in {p["id"] for p in anon.get("/profiles", headers=_h(first)).json()}
    assert early not in {p["id"] for p in anon.get("/profiles", headers=_h(second)).json()}


def test_repeated_wrong_passwords_lock_the_account_briefly(anon):
    _signup(anon, "aditi@example.com")
    for _ in range(FAILED_LOGINS.limit):
        assert anon.post("/auth/login", json={"email": "aditi@example.com", "password": "nope nope"}).status_code == 401
    r = anon.post("/auth/login", json={"email": "aditi@example.com", "password": "correct horse 1"})
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0


@pytest.mark.parametrize("secret", ["", "change-this-secret-in-env", "too-short"])
def test_the_server_refuses_to_start_without_a_strong_secret(monkeypatch, secret):
    monkeypatch.setattr(settings, "auth_secret", secret)
    with pytest.raises(RuntimeError, match="HORMONY_AUTH_SECRET"):
        create_app()


def test_old_auth_databases_keep_each_users_record(tmp_path):
    """The first auth build gave every user one patient_id. Those become profiles the user owns."""
    from sqlalchemy import create_engine, inspect, text
    from hormony.db import migrate_legacy_users
    eng = create_engine(f"sqlite:///{tmp_path}/old.db")
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE users (id VARCHAR(36) PRIMARY KEY, email VARCHAR(255) UNIQUE, "
                          "password_hash VARCHAR(255), patient_id VARCHAR(40) UNIQUE, created_at DATETIME)"))
        conn.execute(text("CREATE TABLE profiles (id VARCHAR(40) PRIMARY KEY, name VARCHAR(60), kind VARCHAR(10), "
                          "cycle_length INTEGER, created_at DATETIME, owner_id VARCHAR(36))"))
        conn.execute(text("INSERT INTO users VALUES ('u1', 'a@example.com', 'h', 'user-a', NULL)"))
    migrate_legacy_users(eng)
    migrate_legacy_users(eng)     # harmless twice
    assert "patient_id" not in {c["name"] for c in inspect(eng).get_columns("users")}
    with eng.connect() as conn:
        assert conn.execute(text("SELECT email FROM users")).scalar() == "a@example.com"
        assert tuple(conn.execute(text("SELECT id, kind, owner_id FROM profiles")).one()) == ("user-a", "personal", "u1")
