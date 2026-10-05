"""Graph wiring, agent isolation, debate/critic inputs, discordance notes, provenance guard."""
import asyncio

from hormony.agents import nodes
from hormony.agents.discordance import compare
from hormony.agents.graph import build_graph
from hormony.agents.provenance import guard
from hormony.agents.schemas import Hypothesis, Rebuttal, Verdict
from tests.fakes import FakeLLM

ALL = ["lab", "symptom", "cycle"]


def _fake(conflict=True):
    if conflict:
        hyps = {"[agent:lab]": Hypothesis(claim="lab", leading_factor="lab_change", confidence=0.78, evidence_ids=["LAB-0801-P4"]),
                "[agent:symptom]": Hypothesis(claim="sym", leading_factor="medication", confidence=0.71, evidence_ids=["MED-0816"]),
                "[agent:cycle]": Hypothesis(claim="cyc", leading_factor="cycle_timing", confidence=0.65, evidence_ids=["CYC-0809"])}
    else:
        hyps = {k: Hypothesis(claim="same", leading_factor="cycle_timing", confidence=0.6, evidence_ids=["CYC-0809"])
                for k in ("[agent:lab]", "[agent:symptom]", "[agent:cycle]")}
    resp = dict(hyps)
    for a in ALL:
        resp[f"[debate:{a}]"] = Rebuttal(text=f"r {a}", evidence_ids=[], revised_confidence=0.5)
    resp["[critic]"] = Verdict(single_cause_supported=False, headline="h", summary="s", overall_confidence=0.5)
    return FakeLLM(resp)


def _go(fake, active=ALL, q="Why fatigue?"):
    return asyncio.run(build_graph(fake).ainvoke({"patient_id": "nancy", "question": q, "active_agents": list(active)}))


def test_conflict_runs_the_debate(seeded):
    out = _go(_fake(True))
    assert out["discordance"]["conflict"] is True and len(out["rebuttals"]) == 3
    assert out["report"]["report"]["headline"] == "h"


def test_agreement_skips_the_debate(seeded):
    fake = _fake(False)
    out = _go(fake)
    assert out["discordance"]["conflict"] is False
    assert not [c for c in fake.calls if "[debate:" in c["system"]]


def test_each_specialist_sees_only_its_own_facts(seeded):
    fake = _fake()
    _go(fake)
    prompts = {c["system"].split("]")[0] + "]": c["user"] for c in fake.calls}
    assert "F-LAB-2" in prompts["[agent:lab]"] and "F-SYM" not in prompts["[agent:lab]"]
    assert "F-SYM-1" in prompts["[agent:symptom]"] and "F-LAB" not in prompts["[agent:symptom]"]
    assert "F-CYC-1" in prompts["[agent:cycle]"] and "F-LAB" not in prompts["[agent:cycle]"]


def test_debate_prompt_has_question_own_facts_and_confidence(seeded):
    fake = _fake()
    _go(fake, q="Why have my fatigue episodes increased?")
    lab = next(c["user"] for c in fake.calls if c["system"].startswith("[debate:lab]"))
    assert "Why have my fatigue episodes increased?" in lab
    assert "F-LAB-2" in lab and "LAB-0926-P4" in lab
    assert "0.78" in lab
    assert "sym" in lab and "cyc" in lab                       # other agents' claims


def test_critic_receives_shared_facts_as_data(seeded):
    fake = _fake()
    _go(fake, active=["symptom", "cycle"])
    crit = next(c["user"] for c in fake.calls if c["system"].startswith("[critic]"))
    assert "F-SHARED-1" in crit and "INPUT_JSON" in crit


def test_paused_agent_never_calls_the_llm(seeded):
    fake = _fake()
    out = _go(fake, active=["symptom", "cycle"])
    assert out["discordance"]["active"] == 2
    assert not [c for c in fake.calls if "[agent:lab]" in c["system"] or "[debate:lab]" in c["system"]]
    assert out["agent_status"]["lab"] == "paused"


def test_fabricated_ids_are_stripped(seeded):
    fake = FakeLLM({"[agent:lab]": Hypothesis(claim="x", leading_factor="lab_change", confidence=0.9,
                                               evidence_ids=["LAB-9999-XX", "LAB-0801-P4"])})
    state = asyncio.run(nodes.scope({"patient_id": "nancy", "question": "q", "active_agents": ["lab"]}))
    out = asyncio.run(nodes.make_specialist("lab", fake)({**state, "question": "q", "active_agents": ["lab"]}))
    assert out["hypotheses"]["lab"]["evidence_ids"] == ["LAB-0801-P4"]


def test_discordance_pairs_have_notes():
    h = lambda f: Hypothesis(claim="c", leading_factor=f, confidence=.6, evidence_ids=[])  # noqa: E731
    d = compare({"lab": h("lab_change"), "cycle": h("cycle_timing"), "symptom": h("medication")})
    rel = {(p["a"], p["b"]): p for p in d["pairs"]}
    assert rel[("cycle", "lab")]["relation"] == "compatible"
    assert "progesterone" in rel[("cycle", "lab")]["note"].lower() or "luteal" in rel[("cycle", "lab")]["note"].lower()
    assert rel[("cycle", "symptom")]["note"] == "Cycle timing vs. medication change as the leading explanation."


def test_guard_caps_confidence_without_verifiable_evidence():
    g = guard(Hypothesis(claim="c", leading_factor="other", confidence=.9, evidence_ids=["NOPE"]), ["LAB-0801-P4"])
    assert g.confidence == .3 and g.evidence_ids == [] and "no verifiable evidence cited" in g.caveats
