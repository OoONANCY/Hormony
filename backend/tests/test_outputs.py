"""Report, why-chain, hypothesis graph and brief are all derived from the data and the verdict."""
import json

from hormony.agents.schemas import Adjustment, Hypothesis, Verdict
from hormony.analysis.features import build_facts, compute_stats
from hormony.ledger.store import load_ledger
from hormony.outputs.hypothesis_graph import build as build_graph
from hormony.outputs.report import build as build_report, build_brief
from tests.conftest import add_event, update_event

ALL = (("lab", .78, .52), ("symptom", .71, .68), ("cycle", .65, .74))


def _verdict(adj=ALL):
    return Verdict(single_cause_supported=False, headline="Your fatigue follows your cycle.", summary="Several factors.",
                   ranked_factors=["cycle_timing"], adjustments=[Adjustment(agent=a, before=b, after=c, reason="r") for a, b, c in adj],
                   unassigned_factors=[], alternatives=["Stress was not logged"], resolve_steps=["Repeat the test"],
                   clinician_questions=["Could timing matter?"], overall_confidence=.6)


def _inputs(pid="nancy"):
    events, starts, today = load_ledger(pid)
    return build_facts(events, starts, today), compute_stats(events, starts, today), {e.id for e in events}


def test_graph_numbers_follow_the_data(seeded):
    add_event(id="SYM-0929-F", date="2026-09-29", type="symptom", name="Fatigue", code="F", severity=7)
    facts, stats, _ = _inputs()
    g = build_graph(stats, _verdict())
    edge = next(e for e in g["edges"] if (e["a"], e["b"]) == ("lut", "fat"))
    assert edge["evidence"] == "14 of 17 fatigue logs"
    assert next(n for n in g["nodes"] if n["id"] == "fat")["sub"] == "17 logs"
    assert next(f.statement for f in facts["cycle"] if f.id == "F-CYC-1").startswith("14 of 17")


def test_graph_edges_cite_ledger_ids(seeded):
    _, stats, ids = _inputs()
    g = build_graph(stats, _verdict())
    for e in g["edges"]:
        if e["type"] != "Untested":
            assert e["evidence_ids"], e
        assert set(e["evidence_ids"]) <= ids, e


def test_paused_agent_edge_has_no_confidence(seeded):
    _, stats, _ = _inputs()
    g = build_graph(stats, _verdict(adj=ALL[1:]))
    lab_edge = next(e for e in g["edges"] if e["b"] == "fat" and e["a"] == "p4")
    assert lab_edge["confidence"] is None
    assert next(e for e in g["edges"] if (e["a"], e["b"]) == ("lut", "fat"))["confidence"] == .74


def test_measured_panels_remove_the_untested_node(seeded):
    add_event(id="LAB-0928-FER", date="2026-09-28", type="lab", name="Ferritin", code="FER", value=18, unit="ng/mL")
    add_event(id="LAB-0928-B12", date="2026-09-28", type="lab", name="Vitamin B12", code="B12", value=410, unit="pg/mL")
    _, stats, _ = _inputs()
    g = build_graph(stats, _verdict())
    assert "iron" not in {n["id"] for n in g["nodes"]}
    assert not [e for e in g["edges"] if e["type"] == "Untested"]


def test_brief_follows_the_data(seeded):
    update_event("LAB-0926-P4", value=9.9)
    _, stats, _ = _inputs()
    b = build_brief(_verdict(), stats)
    labs = next(o for o in b["observations"] if o["kind"] == "lab")
    assert "7.9 → 9.9 ng/mL" in labs["text"]
    assert [o["text"] for o in b["observations"]] == b["observed"]
    assert b["questions"] == ["Could timing matter?"]
    assert "Could timing matter?" in b["text"] and "9.9" in b["text"]


def test_report_sources_count_the_ledger_window(seeded):
    facts, stats, _ = _inputs()
    rep = build_report(facts, {}, _verdict(), stats)
    assert rep["why_chain"]["sources"] == {"cycle": 3, "lab": 10, "symptom": 26, "sleep": 89, "med": 1}


def test_why_chain_observations_are_the_cited_facts(seeded):
    facts, stats, ids = _inputs()
    hyps = {"lab": Hypothesis(claim="c", leading_factor="lab_change", confidence=.7, evidence_ids=["LAB-0926-P4"])}
    rep = build_report(facts, hyps, _verdict(), stats)
    obs = rep["why_chain"]["observations"]
    assert [o["id"] for o in obs] == ["F-LAB-2"]
    assert all(set(o["evidence_ids"]) <= ids for o in obs)


def test_outputs_use_no_diagnostic_language(seeded):
    facts, stats, _ = _inputs()
    v = _verdict()
    blob = json.dumps({"r": build_report(facts, {}, v, stats), "g": build_graph(stats, v)}).lower()
    assert "diagnos" not in blob
    brief = build_brief(v, stats)
    assert "not a diagnosis" in brief["footer"].lower()
    assert "diagnos" not in json.dumps(brief["observations"]).lower()


def test_unmeasured_labs_are_described_as_not_measured(seeded):
    _, stats, _ = _inputs()
    labs = next(o for o in build_brief(_verdict(), stats)["observations"] if o["kind"] == "lab")
    assert "iron/ferritin and B12 not measured in the last 91 days" in labs["text"]
    untested = next(e for e in build_graph(stats, _verdict())["edges"] if e["type"] == "Untested")
    assert untested["evidence"] == "Iron/ferritin and B12 not measured in the last 91 days"
