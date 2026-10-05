"""Insight report, "Why?" chain and clinician brief, rendered from computed stats + the critic's verdict."""
from __future__ import annotations

from typing import Dict, List, Optional

from ..analysis.features import lname, num

FOOTER = ("Not a diagnosis. Hormony surfaces time-based associations in self-reported and uploaded data "
          "so you can have a better-informed conversation with your clinician.")


def _dump(x):
    return x.model_dump() if hasattr(x, "model_dump") else (x or {})


def confidence_word(c: float) -> str:
    return "Low" if c < 0.55 else "Medium" if c < 0.7 else "Medium-high"


def build(facts: Dict[str, list], hypotheses: Dict[str, object], verdict, stats: dict) -> dict:
    v = _dump(verdict)
    hyps = {k: _dump(h) for k, h in (hypotheses or {}).items() if h}
    cited = {i for h in hyps.values() for i in h.get("evidence_ids", [])}
    observations = [_dump(f) for group in ("lab", "symptom", "cycle", "shared") for f in facts.get(group, [])
                    if cited & set(_dump(f).get("evidence_ids", []))]
    adj = {a["agent"]: a for a in (_dump(x) for x in v.get("adjustments", []))}
    views = []
    for agent in ("lab", "symptom", "cycle"):
        h = hyps.get(agent)
        before = float(h["confidence"]) if h else None
        after = float(adj[agent]["after"]) if agent in adj else before
        views.append({"agent": agent, "claim": h["claim"] if h else "", "before": before, "after": after})
    conf = float(v.get("overall_confidence", 0))
    steps = v.get("resolve_steps", [])
    return {
        "headline": v.get("headline", ""),
        "confidence": conf,
        "confidence_word": confidence_word(conf),
        "why_chain": {"sources": dict(stats.get("counts") or {}), "observations": observations,
                      "reasoning": v.get("summary", ""), "confidence": conf, "alternatives": v.get("alternatives", [])},
        "agent_views": views,
        "experiment": steps[0] if steps else "",
    }


def _observations(stats: dict) -> List[dict]:
    out: List[dict] = []
    focus, med, labs, sl = stats.get("focus"), stats.get("med"), stats.get("labs"), stats.get("sleep")
    f_low = lname(focus["name"]) if focus else ""
    if focus:
        out.append({"kind": "symptom", "title": "Symptom clustering",
                    "text": f"{focus['late_n']} of {focus['n']} {f_low} logs fell on cycle days 20–28, across "
                            f"{focus['cycles_with']} of {focus['cycles_total']} cycles observed."})
    if labs:
        parts = []
        for c in labs["comparisons"]:
            when = f"Day-{c['cd']} {lname(c['name'])}" if c["cd"] else c["name"]
            parts.append(f"{when} {num(c['v1'])} → {num(c['v2'])} {c['unit']} ({c['d1']} vs {c['d2']})"
                         + (", stable" if c["stable"] else ""))
        parts += [f"{m['name']} {num(m['value'])} {m['unit']} ({m['date']})" for m in labs["measured"]]
        if labs["missing"]:
            parts.append(f"{' and '.join(labs['missing'])} not measured in the last {stats['window_days']} days")
        out.append({"kind": "lab", "title": "Laboratory measurements", "text": "; ".join(parts) + "."})
    if med and focus:
        trend = "rose" if med["post"] > med["pre"] else "fell" if med["post"] < med["pre"] else "stayed level"
        out.append({"kind": "med", "title": "Medication timing",
                    "text": f"{focus['name']} logs {trend} from {med['pre']} in the {med['days_before']} days before starting "
                            f"{med['name']} ({med['label']}) to {med['post']} in the {med['days_after']} days after."})
    if sl:
        parts = []
        if med and sl.get("before_avg") is not None and sl.get("after_avg") is not None:
            parts.append(f"on nights outside cycle days 20–28, average sleep went from {sl['before_avg']:.1f} h before "
                         f"{med['label']} to {sl['after_avg']:.1f} h after")
        if sl.get("late_avg") is not None and sl.get("other_avg") is not None:
            parts.append(f"late-luteal nights averaged {sl['late_avg']:.1f} h vs {sl['other_avg']:.1f} h on other nights")
        if parts:
            text = "; ".join(parts)
            out.append({"kind": "sleep", "title": "Sleep", "text": text[0].upper() + text[1:] + "."})
    return out


def build_brief(verdict, stats: dict, questions: Optional[List[str]] = None) -> dict:
    v = _dump(verdict)
    obs = _observations(stats)
    qs = questions if questions is not None else list(v.get("clinician_questions", []))
    interp = v.get("summary", "")
    text = "\n".join(["ENDOCRINE INSIGHT REPORT", "", "OBSERVED PATTERNS",
                      *[f"{i + 1}. {o['title']}: {o['text']}" for i, o in enumerate(obs)], "",
                      "SYSTEM INTERPRETATION", interp, "", "QUESTIONS FOR MY CLINICIAN",
                      *[f"• {q}" for q in qs], "", FOOTER])
    return {"observations": obs, "observed": [o["text"] for o in obs], "interpretation": interp,
            "questions": qs, "footer": FOOTER, "text": text}
