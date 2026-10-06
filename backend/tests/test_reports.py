"""Lab-report reading: upload → extract (text LLM / vision LLM / rules) → review → confirm with provenance."""
import asyncio
import base64
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from hormony.agents.llm import AgentUnavailable, OpenRouterLLM, resolve_vision_llm
from hormony.api import routes_reports
from hormony.api.main import create_app
from hormony.config import Settings
from hormony.reports.analytes import normalize
from hormony.reports.extract import ReportExtraction, ReportRow
from hormony.reports.rules import extract_rules
from tests.conftest import make_user
from tests.pdfutil import LAB_REPORT, make_pdf, make_png


class FakeExtractor:
    """Stands in for a text or vision LLM; records what it was given."""

    def __init__(self, name="fake", result=None, fail=False):
        self.name, self.result, self.fail, self.calls = name, result, fail, []

    async def structured(self, system, user, schema, effort="medium"):
        self.calls.append({"user": user})
        if self.fail:
            raise AgentUnavailable("rate limited")
        return self.result

    async def structured_vision(self, system, text, images, schema, effort="medium"):
        self.calls.append({"images": images, "text": text})
        if self.fail:
            raise AgentUnavailable("rate limited")
        return self.result


LLM_RESULT = ReportExtraction(collected_date="2026-10-02", lab_name="City Diagnostics", results=[
    ReportRow(analyte="Prog.", value=4.8, unit="ng/mL", reference_range="1.8-23.9", page=1),
    ReportRow(analyte="Free T4", value=1.2, unit="ng/dL", reference_range="0.8-1.8", page=1),
    ReportRow(analyte="Ferritin", value=14, unit="ng/mL", reference_range="15-150", flag="L", page=2),
])


@pytest.fixture()
def client(seeded, monkeypatch):
    def use(text=None, vision=None):
        monkeypatch.setattr(routes_reports, "text_llm", lambda: text or FakeExtractor(result=LLM_RESULT))
        monkeypatch.setattr(routes_reports, "vision_llm", lambda: vision)
    use()
    with TestClient(create_app(), raise_server_exceptions=False) as c:
        c.headers.update(make_user())
        c.use = use
        yield c


def _upload(c, data, name="report.pdf", ctype="application/pdf", pid="nancy"):
    return c.post(f"/patients/{pid}/reports", files={"file": (name, data, ctype)})


# ---------------- pieces ----------------

def test_analyte_names_are_normalised():
    assert normalize("Prog.") == ("P4", "Progesterone")
    assert normalize("Oestradiol (E2)") == ("E2", "Estradiol")
    assert normalize("Free T4") == ("FT4", "Free T4")
    assert normalize("Vitamin B12") == ("B12", "Vitamin B12")
    assert normalize("25-OH Vitamin D") == ("VITD", "Vitamin D (25-OH)")
    assert normalize("Something Unusual") == (None, "Something Unusual")


def test_rule_based_extraction_reads_a_text_report():
    out = extract_rules(["\n".join(LAB_REPORT)])
    assert out.collected_date == "2026-10-02"
    rows = {r.analyte: r for r in out.results}
    assert set(rows) == {"Progesterone", "Estradiol", "TSH", "Ferritin", "Vitamin B12"}
    assert (rows["Progesterone"].value, rows["Progesterone"].unit, rows["Progesterone"].reference_range) == (4.8, "ng/mL", "1.8-23.9")
    assert rows["Ferritin"].flag == "L"


def test_vision_requests_send_the_image_to_openrouter():
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": LLM_RESULT.model_dump_json()}}]})
    llm = OpenRouterLLM("sk-or", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
                        transport=httpx.MockTransport(handler), retry_delay=0)
    out = asyncio.run(llm.structured_vision("[report] s", "Read this report", [("image/jpeg", b"\xff\xd8jpeg")], ReportExtraction))
    assert out.results[0].value == 4.8
    parts = seen[0]["messages"][1]["content"]
    assert parts[0]["type"] == "text"
    assert parts[1]["image_url"]["url"] == "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8jpeg").decode()


def test_vision_model_needs_an_openrouter_key():
    assert resolve_vision_llm(Settings(openrouter_api_key="")) is None
    v = resolve_vision_llm(Settings(openrouter_api_key="k"))
    assert v.name == "openrouter:nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"


# ---------------- upload → preview ----------------

def test_text_pdf_is_read_by_the_text_llm_and_normalised(client):
    text = FakeExtractor(result=LLM_RESULT)
    client.use(text=text)
    r = _upload(client, make_pdf([LAB_REPORT, ["Page two"]]))
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["method"] == "text" and p["pages"] == 2 and p["collected_date"] == "2026-10-02" and not p["duplicate"]
    assert "=== Page 1 ===" in text.calls[0]["user"] and "Progesterone 4.8" in text.calls[0]["user"]
    rows = {x["code"]: x for x in p["rows"]}
    assert rows["P4"]["analyte"] == "Progesterone" and rows["P4"]["date"] == "2026-10-02"
    assert rows["FT4"]["value"] == 1.2 and rows["FER"]["flag"] == "L" and rows["FER"]["page"] == 2


def test_demo_engine_falls_back_to_rule_based_reading(client):
    client.use(text=FakeExtractor(name="demo"))
    p = _upload(client, make_pdf([LAB_REPORT])).json()
    assert p["method"] == "rules"
    assert {x["code"] for x in p["rows"]} == {"P4", "E2", "TSH", "FER", "B12"}


def test_rate_limited_text_llm_falls_back_with_a_warning(client):
    client.use(text=FakeExtractor(fail=True))
    p = _upload(client, make_pdf([LAB_REPORT])).json()
    assert p["method"] == "rules" and any("check" in w.lower() for w in p["warnings"])


def test_scanned_pdf_goes_to_the_vision_model_as_page_images(client):
    vision = FakeExtractor(result=LLM_RESULT)
    client.use(vision=vision)
    p = _upload(client, make_pdf([[]])).json()
    assert p["method"] == "vision"
    mime, data = vision.calls[0]["images"][0]
    assert mime == "image/jpeg" and data[:2] == b"\xff\xd8"


def test_photo_goes_to_the_vision_model(client):
    vision = FakeExtractor(result=LLM_RESULT)
    client.use(vision=vision)
    p = _upload(client, make_png(), name="IMG_0042.png", ctype="image/png").json()
    assert p["method"] == "vision" and len(vision.calls[0]["images"]) == 1


def test_photo_without_a_vision_model_explains_what_is_needed(client):
    r = _upload(client, make_png(), name="IMG_0042.png", ctype="image/png")
    assert r.status_code == 422 and "OPENROUTER_API_KEY" in r.json()["detail"]


def test_unsupported_and_oversized_files_are_rejected(client):
    assert _upload(client, b"hello", name="notes.txt", ctype="text/plain").status_code == 415
    assert _upload(client, b"\0" * (16 * 1024 * 1024), name="big.pdf").status_code == 413


def test_the_same_file_twice_is_flagged_and_not_re_read(client):
    text = FakeExtractor(result=LLM_RESULT)
    client.use(text=text)
    pdf = make_pdf([LAB_REPORT])
    first = _upload(client, pdf).json()
    again = _upload(client, pdf).json()
    assert again["duplicate"] is True and again["report_id"] == first["report_id"] and len(text.calls) == 1


# ---------------- confirm → ledger ----------------

def _confirm(c, report_id, rows, pid="nancy"):
    return c.post(f"/patients/{pid}/reports/{report_id}/confirm", json={"rows": rows})


def test_confirmed_rows_become_lab_records_that_point_back_to_the_file(client):
    p = _upload(client, make_pdf([LAB_REPORT]), name="Oct labs.pdf").json()
    assert any("after today" in w for w in p["warnings"])          # Oct 2 is in the future for the demo (Sep 29)
    rows = [dict(r, date="2026-09-28") for r in p["rows"] if r["code"] in ("P4", "FER")]
    rows[0]["value"] = 4.9                                     # the user corrected a value and the date in review
    r = _confirm(client, p["report_id"], rows)
    assert r.status_code == 200, r.text
    assert r.json()["added"] == 2
    labs = client.get("/patients/nancy/timeline", params={"types": "lab"}).json()["events"]
    p4 = next(e for e in labs if e["source"] == "Lab report: Oct labs.pdf" and e["code"] == "P4")
    assert p4["value"] == 4.9 and p4["date"] == "2026-09-28" and p4["source_ref"] == f"report:{p['report_id']}#p1"
    assert "1.8-23.9" in p4["note"]
    again = _confirm(client, p["report_id"], rows)
    assert again.json() == {**again.json(), "added": 0, "skipped": 2}


def test_confirm_validates_dates_and_values(client):
    p = _upload(client, make_pdf([LAB_REPORT])).json()
    row = dict(p["rows"][0])
    assert _confirm(client, p["report_id"], [{**row, "date": "2026-10-02"}]).status_code == 400   # future for the demo
    assert _confirm(client, p["report_id"], [{**row, "date": ""}]).status_code == 400
    assert _confirm(client, "nope", [row]).status_code == 404


def test_the_original_file_can_be_opened(client):
    pdf = make_pdf([LAB_REPORT])
    p = _upload(client, pdf, name="Oct labs.pdf").json()
    r = client.get(f"/patients/nancy/reports/{p['report_id']}/file")
    assert r.status_code == 200 and r.content == pdf and r.headers["content-type"] == "application/pdf"


def test_two_people_can_upload_the_same_file_and_only_see_their_own(client):
    """Reports are per person: the same PDF under the demo and a personal profile are two separate readings."""
    pid = client.post("/profiles", json={"name": "Aditi", "last_period_start": "2026-09-20"}).json()["id"]
    pdf = make_pdf([LAB_REPORT])
    mine = _upload(client, pdf, pid=pid)
    assert mine.status_code == 200, mine.text
    assert mine.json()["duplicate"] is False
    rid = mine.json()["report_id"]
    assert client.get(f"/patients/nancy/reports/{rid}/file").status_code == 404      # someone else's file
    assert _confirm(client, rid, mine.json()["rows"][:1], pid="nancy").status_code == 404
    demo = _upload(client, pdf).json()
    assert demo["duplicate"] is False and demo["report_id"] == rid
    rows = [dict(r, date="2026-09-28") for r in demo["rows"]][:1]
    assert _confirm(client, rid, rows, pid="nancy").json()["added"] == 1
    assert client.get(f"/patients/nancy/reports/{rid}/file").status_code == 200
    client.delete(f"/profiles/{pid}")                                                 # deleting one copy keeps the other
    assert client.get(f"/patients/nancy/reports/{rid}/file").status_code == 200


def test_files_that_cannot_be_opened_get_a_clear_message(client):
    """A broken photo or PDF is the user's problem to fix, not a server error."""
    for name, ctype, data in (("photo.png", "image/png", b"\x89PNG\r\n\x1a\n"), ("labs.pdf", "application/pdf", b"%PDF-1.4 garbage")):
        r = _upload(client, data, name=name, ctype=ctype)
        assert r.status_code == 415, (name, r.status_code, r.text)
        assert "couldn't open" in r.json()["detail"].lower()
