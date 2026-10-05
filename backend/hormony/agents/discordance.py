from __future__ import annotations

from typing import Dict

from .schemas import Hypothesis

COMPATIBLE = {
    frozenset({"lab_change", "cycle_timing"}):
        "Progesterone and other luteal-phase labs move with the cycle, so a lab change and cycle timing can point the same way.",
}
PHRASE = {"cycle_timing": "cycle timing", "medication": "medication change", "lab_change": "lab change",
          "sleep": "sleep", "other": "other factors", "insufficient_data": "insufficient data"}


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def compare(hyps: Dict[str, "Hypothesis | None"]) -> dict:
    live = {k: h for k, h in hyps.items() if h is not None}
    names = sorted(live)
    pairs = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            fa, fb = live[a].leading_factor, live[b].leading_factor
            if fa == fb:
                rel, note = "agree", f"Both point to {PHRASE[fa]}."
            elif frozenset({fa, fb}) in COMPATIBLE:
                rel, note = "compatible", COMPATIBLE[frozenset({fa, fb})]
            else:
                rel, note = "conflict", f"{_cap(PHRASE[fa])} vs. {PHRASE[fb]} as the leading explanation."
            pairs.append({"a": a, "b": b, "relation": rel, "note": note})
    return {
        "conflict": any(p["relation"] == "conflict" for p in pairs),
        "pairs": pairs,
        "active": len(live),
        "distinct_factors": len({h.leading_factor for h in live.values()}),
    }
