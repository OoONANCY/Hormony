"""Prompt contract: wording rules every provider receives (the schema text travels with each request)."""
import asyncio
import json

from hormony.agents import prompts
from hormony.agents.llm import DemoLLM, strict_schema
from hormony.agents.schemas import Verdict


def test_every_agent_is_told_that_unmeasured_means_unknown():
    for system in (prompts.specialist_system("lab"), prompts.debate_system("lab"), prompts.critic_system()):
        assert "not measured" in system and "unknown" in system and "not normal" in system


def test_critic_is_told_to_write_first_person_questions_for_a_clinician():
    system = prompts.critic_system()
    assert "first person" in system and "Could my" in system
    assert "never questions addressed to the person" in system


def test_verdict_schema_describes_clinician_questions_as_first_person():
    desc = strict_schema(Verdict)["properties"]["clinician_questions"]["description"]
    assert "first person" in desc and "clinician" in desc


def test_demo_engine_writes_first_person_questions_and_reads_unknown_labs():
    payload = {"focus": "Fatigue",
               "hypotheses": {"lab": {"claim": "Day-21 progesterone 7.9 ng/mL on Aug 1 → 4.2 ng/mL on Sep 26.", "leading_factor": "lab_change",
                                      "confidence": .75, "evidence_ids": ["LAB-0926-P4"], "caveats": []}},
               "rebuttals": {"lab": {"text": "Iron/ferritin and B12 were not measured in the last 91 days, so their status is unknown.",
                                     "evidence_ids": [], "revised_confidence": .5}},
               "shared_facts": []}
    v = asyncio.run(DemoLLM().structured("[critic] s", "Question: q\nINPUT_JSON:" + json.dumps(payload), Verdict))
    assert v.clinician_questions and all(" my " in f" {q} " or q.startswith(("Could I", "Should I", "Would ")) for q in v.clinician_questions)
    assert not [q for q in v.clinician_questions if " you " in f" {q.lower()} " or q.lower().startswith(("how does your", "have you"))]
    assert "Would iron/ferritin or B12 testing be useful for me?" in v.clinician_questions
