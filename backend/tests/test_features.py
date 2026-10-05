"""Deterministic facts: every number and date comes from the ledger, nothing is hard-coded."""
import re

from hormony.analysis.features import build_facts
from hormony.ledger.store import load_ledger
from hormony.schemas import EventOut
from tests.conftest import add_event, update_event


def _facts(pid="nancy"):
    events, starts, today = load_ledger(pid)
    return build_facts(events, starts, today)


def _by_id(facts):
    return {f.id: f for group in facts.values() for f in group}


def test_seed_facts_match_the_prototype(seeded):
    f = _by_id(_facts())
    assert f["F-LAB-1"].statement == "10 lab values across 4 blood draws"
    assert f["F-LAB-2"].statement == "Day-21 progesterone 7.9 ng/mL on Aug 1 → 4.2 ng/mL on Sep 26"
    assert f["F-LAB-2"].evidence_ids == ["LAB-0801-P4", "LAB-0926-P4"]
    assert f["F-LAB-3"].statement == "Day-21 estradiol 132 pg/mL on Aug 1 → 141 pg/mL on Sep 26 (stable)"
    assert f["F-LAB-4"].statement == "Day-25 TSH 2.6 mIU/L on Jul 8 → 2.4 mIU/L on Sep 2 (stable)"
    assert f["F-LAB-5"].statement == "Iron/ferritin and B12 were not measured in the last 91 days, so their status is unknown"
    assert f["F-LAB-5"].evidence_ids == []
    assert f["F-SYM-1"].statement == ("Fatigue: 5 logs in the 46 days before Spironolactone 50 mg started on Aug 16 "
                                      "→ 11 in the 45 days after")
    assert f["F-SYM-1"].evidence_ids[0] == "MED-0816"
    assert f["F-SYM-2"].statement == "3 post-change fatigue logs fall outside cycle days 20–28"
    assert f["F-SYM-2"].evidence_ids == ["SYM-0819-F", "SYM-0822-F", "SYM-0912-F"]
    assert f["F-SYM-3"].statement == "Anxiety appeared within a day of fatigue in 4 of 4 logs"
    assert f["F-CYC-1"].statement == "13 of 16 fatigue logs fall on cycle days 20–28"
    assert f["F-CYC-2"].statement == "The pattern repeats in 4 of 4 cycles"
    late, other = map(float, re.search(r"average (\d+\.\d) h vs (\d+\.\d) h", f["F-CYC-3"].statement).groups())
    assert late < other
    before, after = map(float, re.search(r"(\d+\.\d) h before Aug 16 → (\d+\.\d) h after", f["F-SHARED-1"].statement).groups())
    assert after < before
    assert re.match(r"\d+ of 16 fatigue days followed a night under 6\.5 h", f["F-SHARED-2"].statement)


def test_every_cited_id_is_in_the_ledger(seeded):
    events, starts, today = load_ledger("nancy")
    ids = {e.id for e in events}
    for f in _by_id(build_facts(events, starts, today)).values():
        assert set(f.evidence_ids) <= ids, (f.id, f.evidence_ids)


def test_lab_facts_follow_the_data(seeded):
    update_event("LAB-0926-P4", value=9.9)
    add_event(id="LAB-0928-FER", date="2026-09-28", type="lab", name="Ferritin", code="FER", value=18, unit="ng/mL")
    add_event(id="LAB-0928-B12", date="2026-09-28", type="lab", name="Vitamin B12", code="B12", value=410, unit="pg/mL")
    statements = [f.statement for f in _by_id(_facts()).values()]
    assert "Day-21 progesterone 7.9 ng/mL on Aug 1 → 9.9 ng/mL on Sep 26" in statements
    assert not [s for s in statements if "not measured" in s]
    assert "Ferritin 18 ng/mL on Sep 28" in statements


def test_medication_date_follows_the_data(seeded):
    update_event("MED-0816", date="2026-08-20")
    f = _by_id(_facts())
    assert f["F-SYM-1"].statement == ("Fatigue: 6 logs in the 50 days before Spironolactone 50 mg started on Aug 20 "
                                      "→ 10 in the 41 days after")
    assert "before Aug 20" in f["F-SHARED-1"].statement


def test_build_facts_does_not_mutate_its_input(seeded):
    events, starts, today = load_ledger("nancy")
    legacy = [EventOut(**{**e.model_dump(), "type": {"cycle": "cyc", "symptom": "sym", "sleep": "slp"}.get(e.type, e.type)})
              for e in events]
    build_facts(legacy, starts, today)
    assert {e.type for e in legacy} >= {"cyc", "sym", "slp"}


def test_empty_ledger_yields_no_unsupported_facts(seeded):
    facts = _facts("ghost")
    assert all(not f.evidence_ids for f in _by_id(facts).values())


def test_a_single_missing_panel_reads_as_unknown(seeded):
    from tests.conftest import add_event
    add_event(id="LAB-0928-FER", date="2026-09-28", type="lab", name="Ferritin", code="FER", value=18, unit="ng/mL")
    statements = [f.statement for f in _by_id(_facts()).values()]
    assert "B12 was not measured in the last 91 days, so its status is unknown" in statements
