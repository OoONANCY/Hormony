"""Evidence-backed hypothesis graph built from computed stats. Edge confidence comes from the agent that
assessed that link (critic-adjusted); links no agent assessed carry no confidence."""
from __future__ import annotations

from typing import Dict, Optional

from ..analysis.features import lname, num

MAX_IDS = 6


def _dump(x):
    return x.model_dump() if hasattr(x, "model_dump") else (x or {})


def build(stats: dict, verdict, hypotheses: Optional[Dict[str, object]] = None) -> dict:
    v = _dump(verdict)
    adjusted = {a["agent"]: float(a["after"]) for a in (_dump(x) for x in v.get("adjustments", []))}
    hyps = {k: _dump(h) for k, h in (hypotheses or {}).items() if h}

    def conf(agent: str) -> Optional[float]:
        if agent in adjusted:
            return adjusted[agent]
        return float(hyps[agent]["confidence"]) if agent in hyps else None

    nodes, edges = [], []
    focus, med, labs, sl = stats.get("focus"), stats.get("med"), stats.get("labs"), stats.get("sleep")
    if not focus:
        return {"nodes": nodes, "edges": edges}
    f_low = lname(focus["name"])
    alts_sleep = ["Sleep was also shorter in this window"] if sl and sl.get("late_avg") and sl.get("other_avg") \
        and sl["late_avg"] < sl["other_avg"] else []

    def edge(a, b, type_, evidence, ids, window, agent, alternatives):
        edges.append({"a": a, "b": b, "type": type_, "evidence": evidence, "evidence_ids": list(ids)[:MAX_IDS],
                      "window": window, "agent": agent, "confidence": conf(agent) if agent else None,
                      "alternatives": alternatives})

    nodes.append({"id": "fat", "label": focus["name"], "sub": f"{focus['n']} logs", "type": "symptom"})
    if focus["late_ids"]:
        nodes.append({"id": "lut", "label": "Late luteal", "sub": "days 20–28", "type": "cycle"})
        edge("lut", "fat", "Temporal association", f"{focus['late_n']} of {focus['n']} {f_low} logs", focus["late_ids"],
             f"Cycle days 20–28, {focus['cycles_with']} of {focus['cycles_total']} cycles", "cycle",
             alts_sleep + ["Symptoms may be noticed more late in the cycle"])
    if med:
        nodes.append({"id": "med", "label": med["short"], "sub": f"from {med['label']}", "type": "med"})
        edge("med", "fat", "Before / after association", f"{med['pre']} → {med['post']} {f_low} logs",
             [med["id"]] + med["post_ids"], f"{med['days_before']} days before vs {med['days_after']} days after {med['label']}",
             "symptom", (["Sleep also changed after the start date"] if sl and sl.get("after_avg") is not None
                         and sl.get("before_avg") is not None and sl["after_avg"] != sl["before_avg"] else [])
             + ["Only one medication change observed"])
    if labs and labs["comparisons"]:
        moving = [c for c in labs["comparisons"] if not c["stable"]] or labs["comparisons"]
        c = moving[0]
        nid = "p4" if str(c["code"]).upper() == "P4" else f"lab-{str(c['code']).lower()}"
        arrow = {"down": "↓", "up": "↑"}.get(c["direction"], "→")
        nodes.append({"id": nid, "label": f"{c['name']} {arrow}", "sub": f"day {c['cd']}" if c["cd"] else "first vs last",
                      "type": "lab"})
        edge(nid, "fat", "Co-occurrence", f"{num(c['v1'])} → {num(c['v2'])} {c['unit']}, 2 samples",
             [c["id1"], c["id2"]], f"{c['d1']} vs {c['d2']}", "lab",
             ["Normal cycle-to-cycle variation", "Single-sample lab noise"])
    if sl and sl.get("short_ids"):
        nodes.append({"id": "slp", "label": "Short sleep", "sub": "< 6.5 h", "type": "sleep"})
        edge("slp", "fat", "Co-occurrence (not assessed by an agent)",
             f"{sl['short_before']} of {focus['n']} {f_low} days followed a night under 6.5 h", sl["short_ids"],
             "The night before", None, ["The link could run the other way", "Both may follow cycle timing"])
        if focus["late_ids"] and sl.get("late_ids") and sl.get("late_avg") is not None and sl.get("other_avg") is not None:
            edge("lut", "slp", "Temporal association (not assessed by an agent)",
                 f"Late-luteal nights {sl['late_avg']:.1f} h vs {sl['other_avg']:.1f} h", sl["late_ids"],
                 "Cycle days 20–28", None, ["Stress or schedule changes were not logged"])
        if med and sl.get("after_ids") and sl.get("before_avg") is not None and sl.get("after_avg") is not None:
            edge("med", "slp", "Before / after association (not assessed by an agent)",
                 f"Average sleep {sl['before_avg']:.1f} h → {sl['after_avg']:.1f} h", sl["after_ids"],
                 f"Nights outside days 20–28, before vs after {med['label']}", None, ["Seasonal or schedule change"])
    if stats.get("cooccur"):
        c = stats["cooccur"][0]
        if c["co"]:
            nodes.append({"id": "anx", "label": c["name"], "sub": f"{c['n']} logs", "type": "symptom"})
            edge("fat", "anx", "Co-occurrence (not assessed by an agent)",
                 f"{c['co']} of {c['n']} {lname(c['name'])} logs within a day of {f_low}", c["ids"], "± 1 day", None,
                 ["Few logs so far"])
    if labs and labs["missing"]:
        nodes.append({"id": "iron", "label": " / ".join(labs["missing"]), "sub": "not measured", "type": "ghost"})
        edges.append({"a": "iron", "b": "fat", "type": "Untested", "agent": None, "confidence": None,
                      "evidence": f"{' and '.join(labs['missing'])[:1].upper()}{' and '.join(labs['missing'])[1:]} "
                                  f"not measured in the last {stats['window_days']} days",
                      "evidence_ids": [], "window": "—", "alternatives": ["Ask a clinician whether testing would help"]})
    return {"nodes": nodes, "edges": edges}
