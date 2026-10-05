"""Deterministic facts per agent. Every number, date, analyte and medication comes from the ledger.

`compute_stats` is the single source of truth; facts, the hypothesis graph and the clinician brief
are all rendered from it, so they always agree with each other and with the data. LLMs only
interpret these facts.
"""
from __future__ import annotations

from collections import Counter
from datetime import date as Date, timedelta
from typing import Dict, List, Optional, Tuple

from ..agents.schemas import Fact
from ..ledger import cycle as cyc
from ..schemas import EventOut

WINDOW_DAYS = 91          # the timeline window: today and the 90 days before it
SHORT_NIGHT_H = 6.5
MAX_IDS = 4               # evidence IDs quoted per fact (keeps prompts short)
CODE_ORDER = ["P4", "E2", "TSH"]
PANELS = {                # panels whose absence is itself a finding
    "iron/ferritin": ({"FER", "FERRITIN", "IRON", "FE", "TSAT"}, ("ferritin", "iron")),
    "B12": ({"B12", "VITB12", "COBALAMIN"}, ("b12", "cobalamin")),
}
_MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def label(d: Date) -> str:
    return f"{_MON[d.month - 1]} {d.day}"


def num(v: float) -> str:
    return f"{v:g}"


def lname(name: str) -> str:
    return name if name.isupper() else name.lower()


def not_measured(missing: List[str], days: int) -> str:
    """An unmeasured panel has an unknown status; say so explicitly so it is never read as normal."""
    names = " and ".join(missing)
    names = names[0].upper() + names[1:]
    return (f"{names} was not measured in the last {days} days, so its status is unknown" if len(missing) == 1
            else f"{names} were not measured in the last {days} days, so their status is unknown")


def _avg(xs: List[float]) -> Optional[float]:
    return round(sum(xs) / len(xs), 2) if xs else None


def _cycles_in_window(starts: List[Date], lo: Date, today: Date) -> List[Date]:
    s = sorted(x for x in starts if x <= today)
    out = []
    for i, start in enumerate(s):
        end = s[i + 1] - timedelta(days=1) if i + 1 < len(s) else today
        if end >= lo:
            out.append(start)
    return out


def _cycle_of(d: Date, cycles: List[Date]) -> Optional[Date]:
    prior = [c for c in cycles if c <= d]
    return max(prior) if prior else None


def _lab_comparison(samples: List[EventOut], starts: List[Date]) -> Optional[dict]:
    """Prefer the same cycle day (most recent pair), else first vs last."""
    samples = sorted(samples, key=lambda e: (e.date, e.id))
    if len(samples) < 2:
        return None
    by_cd: Dict[int, List[EventOut]] = {}
    for e in samples:
        cd = cyc.cycle_day(e.date, starts)
        if cd:
            by_cd.setdefault(cd, []).append(e)
    pairs = [(cd, g) for cd, g in by_cd.items() if len(g) >= 2]
    if pairs:
        cd, group = max(pairs, key=lambda p: (p[1][-1].date, len(p[1])))
        a, b = group[0], group[-1]
    else:
        cd, a, b = None, samples[0], samples[-1]
    stable = bool(a.value) and abs(b.value - a.value) / abs(a.value) < 0.10
    return {"code": a.code or a.name, "name": a.name, "unit": a.unit or "", "cd": cd,
            "v1": a.value, "v2": b.value, "d1": label(a.date), "d2": label(b.date),
            "id1": a.id, "id2": b.id, "stable": stable,
            "direction": "flat" if stable else ("down" if b.value < a.value else "up")}


def compute_stats(events: List[EventOut], starts: List[Date], today: Date, window_days: int = WINDOW_DAYS) -> dict:
    lo = today - timedelta(days=window_days - 1)
    ev = [e for e in events if lo <= e.date <= today]
    t = lambda e: cyc.canon_type(e.type)  # noqa: E731  (never mutate the caller's events)
    of = lambda kind: [e for e in ev if t(e) == kind]  # noqa: E731
    cd_of = lambda d: cyc.cycle_day(d, starts)  # noqa: E731
    stats: dict = {"window_days": window_days, "window_start": lo.isoformat(), "today": today.isoformat(),
                   "counts": {k: len(of(k)) for k in ("cycle", "lab", "symptom", "sleep", "med")},
                   "focus": None, "med": None, "trend": None, "cooccur": [], "labs": None, "sleep": None}

    # ---- focus symptom: the most-logged one ----
    syms = of("symptom")
    counts = Counter(e.name for e in syms)
    focus_name = sorted(counts, key=lambda n: (-counts[n], n))[0] if counts else None
    fat = sorted([e for e in syms if e.name == focus_name], key=lambda e: (e.date, e.id))
    cycles = _cycles_in_window(starts, lo, today)
    start_ids = {e.date: e.id for e in events if t(e) == "cycle" and cyc.is_period_start(e.name, e.code)}
    if focus_name:
        late = [e for e in fat if cyc.is_late(cd_of(e.date))]
        with_late = sorted({_cycle_of(e.date, cycles) for e in late} - {None})
        stats["focus"] = {"name": focus_name, "n": len(fat), "ids": [e.id for e in fat],
                          "late_n": len(late), "late_ids": [e.id for e in late],
                          "cycles_total": len(cycles), "cycles_with": len(with_late),
                          "cycle_start_ids": [start_ids[c] for c in with_late if c in start_ids]}

    # ---- medication change: the first one in the window ----
    meds = sorted(of("med"), key=lambda e: (e.date, e.id))
    if meds and focus_name:
        m = meds[0]
        pre = [e for e in fat if e.date < m.date]
        post = [e for e in fat if e.date >= m.date]
        off = [e for e in post if not cyc.is_late(cd_of(e.date))]
        stats["med"] = {"id": m.id, "name": m.name, "short": m.name.split()[0], "date": m.date.isoformat(),
                        "label": label(m.date), "days_before": (m.date - lo).days, "days_after": (today - m.date).days + 1,
                        "pre": len(pre), "post": len(post), "pre_ids": [e.id for e in pre],
                        "post_ids": [e.id for e in post], "off_ids": [e.id for e in off]}
    elif focus_name:
        mid = lo + timedelta(days=window_days // 2)
        first = [e for e in fat if e.date < mid]
        stats["trend"] = {"first": len(first), "second": len(fat) - len(first), "split": label(mid),
                          "first_days": (mid - lo).days, "second_days": (today - mid).days + 1}

    # ---- symptoms that travel with the focus symptom ----
    fdays = [e.date for e in fat]
    for name in sorted((n for n in counts if n != focus_name and counts[n] >= 2), key=lambda n: (-counts[n], n)):
        logs = sorted([e for e in syms if e.name == name], key=lambda e: (e.date, e.id))
        co = [a for a in logs if any(abs((a.date - d).days) <= 1 for d in fdays)]
        stats["cooccur"].append({"name": name, "co": len(co), "n": len(logs), "ids": [e.id for e in co]})

    # ---- labs ----
    labs = [e for e in of("lab") if e.value is not None]
    if labs:
        groups: Dict[str, List[EventOut]] = {}
        for e in labs:
            groups.setdefault((e.code or e.name).upper(), []).append(e)
        order = sorted(groups, key=lambda c: (CODE_ORDER.index(c) if c in CODE_ORDER else len(CODE_ORDER), c))
        comps = [c for c in (_lab_comparison(groups[k], starts) for k in order) if c]
        measured, missing = [], []
        for panel, (codes, words) in PANELS.items():
            hits = [e for e in labs if (e.code or "").upper() in codes or any(w in e.name.lower() for w in words)]
            if hits:
                last = max(hits, key=lambda e: (e.date, e.id))
                measured.append({"panel": panel, "name": last.name, "value": last.value, "unit": last.unit or "",
                                 "date": label(last.date), "id": last.id})
            else:
                missing.append(panel)
        stats["labs"] = {"n": len(labs), "draws": len({e.date for e in labs}), "comparisons": comps,
                         "measured": measured, "missing": missing}

    # ---- sleep (a night counts toward the cycle day it leads into) ----
    nights: Dict[Date, EventOut] = {}
    for e in sorted(of("sleep"), key=lambda e: (e.date, e.id)):
        if e.value is not None:
            nights[e.date] = e
    if nights:
        late_n = lambda d: cyc.is_late(cd_of(d + timedelta(days=1)))  # noqa: E731
        s = {"late_avg": _avg([e.value for d, e in nights.items() if late_n(d)]),
             "other_avg": _avg([e.value for d, e in nights.items() if not late_n(d)]),
             "late_ids": [e.id for d, e in nights.items() if late_n(d)], "n": len(nights)}
        if stats["med"]:
            md = Date.fromisoformat(stats["med"]["date"])
            before = [e for d, e in nights.items() if d < md and not late_n(d)]
            after = [e for d, e in nights.items() if d >= md and not late_n(d)]
            s.update(before_avg=_avg([e.value for e in before]), after_avg=_avg([e.value for e in after]),
                     after_ids=[e.id for e in after])
        if fat:
            prev = [nights.get(e.date - timedelta(days=1)) for e in fat]
            short = [p for p in prev if p is not None and p.value < SHORT_NIGHT_H]
            s.update(short_before=len(short), short_ids=[p.id for p in short])
        stats["sleep"] = s
    return stats


def analyze(events: List[EventOut], starts: List[Date], today: Date) -> Tuple[Dict[str, List[Fact]], dict]:
    st = compute_stats(events, starts, today)
    focus, med, labs, sl = st["focus"], st["med"], st["labs"], st["sleep"]
    f_low = lname(focus["name"]) if focus else ""
    lab: List[Fact] = []
    sym: List[Fact] = []
    cy: List[Fact] = []
    shared: List[Fact] = []
    add = lambda group, prefix, statement, ids=(): group.append(  # noqa: E731
        Fact(id=f"{prefix}-{len(group) + 1}", statement=statement, evidence_ids=list(ids)[:MAX_IDS]))

    if labs:
        add(lab, "F-LAB", f"{labs['n']} lab values across {labs['draws']} blood draws")
        for c in labs["comparisons"]:
            when = f"Day-{c['cd']} {lname(c['name'])}" if c["cd"] else c["name"]
            text = f"{when} {num(c['v1'])} {c['unit']} on {c['d1']} → {num(c['v2'])} {c['unit']} on {c['d2']}"
            add(lab, "F-LAB", text.replace("  ", " ") + (" (stable)" if c["stable"] else ""), [c["id1"], c["id2"]])
        for m in labs["measured"]:
            add(lab, "F-LAB", f"{m['name']} {num(m['value'])} {m['unit']} on {m['date']}".replace("  ", " "), [m["id"]])
        if labs["missing"]:
            add(lab, "F-LAB", not_measured(labs["missing"], st["window_days"]))

    if focus:
        if med:
            add(sym, "F-SYM", f"{focus['name']}: {med['pre']} logs in the {med['days_before']} days before {med['name']} "
                              f"started on {med['label']} → {med['post']} in the {med['days_after']} days after",
                [med["id"]] + med["pre_ids"][:1] + med["post_ids"][:2])
            if med["off_ids"]:
                add(sym, "F-SYM", f"{len(med['off_ids'])} post-change {f_low} logs fall outside cycle days 20–28", med["off_ids"])
        elif st["trend"]:
            tr = st["trend"]
            add(sym, "F-SYM", f"{focus['name']}: {tr['first']} logs in the first {tr['first_days']} days → "
                              f"{tr['second']} in the last {tr['second_days']} days", focus["ids"][-MAX_IDS:])
        for c in st["cooccur"]:
            add(sym, "F-SYM", f"{c['name']} appeared within a day of {f_low} in {c['co']} of {c['n']} logs", c["ids"])

        add(cy, "F-CYC", f"{focus['late_n']} of {focus['n']} {f_low} logs fall on cycle days 20–28", focus["late_ids"])
        if focus["cycles_total"]:
            add(cy, "F-CYC", f"The pattern repeats in {focus['cycles_with']} of {focus['cycles_total']} cycles",
                focus["cycle_start_ids"])
    if sl and sl["late_avg"] is not None and sl["other_avg"] is not None:
        add(cy, "F-CYC", f"Late-luteal nights average {sl['late_avg']:.1f} h vs {sl['other_avg']:.1f} h on other nights")
    if sl and med and sl.get("before_avg") is not None and sl.get("after_avg") is not None:
        add(shared, "F-SHARED", f"On comparable nights (outside cycle days 20–28), sleep averaged {sl['before_avg']:.1f} h "
                                f"before {med['label']} → {sl['after_avg']:.1f} h after")
    if sl and focus and "short_before" in sl:
        add(shared, "F-SHARED", f"{sl['short_before']} of {focus['n']} {f_low} days followed a night under "
                                f"{num(SHORT_NIGHT_H)} h", sl["short_ids"])
    return {"lab": lab, "symptom": sym, "cycle": cy, "shared": shared}, st


def build_facts(events: List[EventOut], starts: List[Date], today: Date) -> Dict[str, List[Fact]]:
    return analyze(events, starts, today)[0]
