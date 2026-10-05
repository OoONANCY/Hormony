from __future__ import annotations

import json
from typing import Iterable, List, Tuple

from .schemas import Fact

ROLE = {"lab": "lab-results", "symptom": "symptom-pattern", "cycle": "cycle-timing"}

SHARED_RULES = (
    "Use only the facts provided. Do not introduce numbers that are not in the facts. "
    "Cite ledger IDs from the facts in `evidence_ids`. Describe associations, never causes or diagnoses. "
    "Use non-diagnostic language (associated with, may, hypothesis). "
    "A test that was not measured has an unknown status: it is not normal and not abnormal, so never describe it "
    "as normal, fine or 'no deficit'."
)


def fact_lines(facts: Iterable[Fact]) -> str:
    return "\n".join(f"- ({f.id}) {f.statement} [IDs: {', '.join(f.evidence_ids) or 'none'}]" for f in facts)


def specialist_system(agent: str) -> str:
    return (f"[agent:{agent}] You are the {ROLE.get(agent, agent)} specialist on a team reviewing one person's hormone, "
            f"symptom, cycle, sleep and medication records. Form one hypothesis that answers the question from your "
            f"facts alone. If your facts don't support a claim, set `leading_factor` to `insufficient_data`. {SHARED_RULES}")


def specialist_user(question: str, facts: List[Fact]) -> str:
    return f"Question: {question}\nFacts:\n{fact_lines(facts)}\n"


def debate_system(agent: str) -> str:
    return (f"[debate:{agent}] You are the {ROLE.get(agent, agent)} specialist. The other specialists reached different "
            f"conclusions. In 1-3 sentences, defend or revise your hypothesis using only your facts, cite ledger IDs, "
            f"and give your revised confidence. {SHARED_RULES}")


def debate_user(question: str, own_claim: str, own_conf: float, facts: List[Fact], others: List[Tuple[str, str]]) -> str:
    return (f"Question: {question}\nYour hypothesis (confidence {own_conf:.2f}): {own_claim}\n"
            f"Your facts:\n{fact_lines(facts)}\nOther agents:\n" + "\n".join(f"- {a}: {c}" for a, c in others) + "\n")


def critic_system() -> str:
    return ("[critic] You are the reasoning critic. Weigh every hypothesis against the evidence it cites and the "
            "rebuttals. Adjust each agent's confidence (explain why in `reason`). List factors that no agent owned, "
            "using the shared facts. Do not name a single cause unless the evidence supports it. `headline` is one "
            "plain sentence for the person. `clinician_questions` are written in the first person, as questions the "
            "person will ask their clinician (e.g. \"Could my fatigue be related to the medication change?\", "
            "\"Should my day-21 progesterone be rechecked?\"); never questions addressed to the person. "
            f"{SHARED_RULES}")


def critic_user(question: str, payload: dict) -> str:
    return f"Question: {question}\nINPUT_JSON:{json.dumps(payload, ensure_ascii=False)}"
