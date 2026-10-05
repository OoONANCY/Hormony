from __future__ import annotations
from .schemas import Hypothesis


def guard(h: Hypothesis, ledger_ids: list[str]) -> Hypothesis:
    allowed = set(ledger_ids)
    kept = [i for i in h.evidence_ids if i in allowed]
    dropped = len(kept) != len(h.evidence_ids)
    data = h.model_dump()
    data["evidence_ids"] = kept
    caves = list(data.get("caveats") or [])
    if not kept:
        data["confidence"] = min(float(data.get("confidence", 0)), 0.3)
        if "no verifiable evidence cited" not in caves:
            caves.append("no verifiable evidence cited")
    elif dropped and "some cited IDs were not verifiable and were removed" not in caves:
        caves.append("some cited IDs were not verifiable and were removed")
    data["caveats"] = caves
    return Hypothesis(**data)
