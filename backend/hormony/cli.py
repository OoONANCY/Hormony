"""Run one analysis from the terminal (the same pipeline the API uses) and save it.

    python -m hormony.cli ask "Why have my fatigue episodes increased?"           # provider from .env
    python -m hormony.cli ask "..." --demo --pause lab                           # offline demo engine
    python -m hormony.cli ask "..." --demo --golden sample_data/golden_run.json  # refresh the replay recording
"""
from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from typing import List, Optional

from . import runner
from .agents.llm import DemoLLM, resolve_llm
from .config import settings
from .db import SessionLocal, init_db
from .ledger.seed import seed_db
from .models import AnalysisRun, Event

DEFAULT_Q = "Why have my fatigue episodes increased over the last two cycles?"


def main(argv: Optional[List[str]] = None) -> str:
    ap = argparse.ArgumentParser(prog="python -m hormony.cli")
    ap.add_argument("args", nargs="*", help='ask "question"')
    ap.add_argument("--patient", default="nancy")
    ap.add_argument("--pause", default="", help="comma-separated agents to pause (lab,symptom,cycle)")
    ap.add_argument("--demo", action="store_true", help="use the offline demo engine (no network)")
    ap.add_argument("--seed", action="store_true", help="re-seed the demo ledger first (replaces this patient's events)")
    ap.add_argument("--golden", default="", help="also write the run as a replay recording to this path")
    a = ap.parse_args(argv)
    parts = a.args[1:] if a.args and a.args[0] == "ask" else a.args
    question = " ".join(parts).strip() or DEFAULT_Q

    init_db()
    db = SessionLocal()
    try:
        empty = db.query(Event).filter(Event.patient_id == a.patient).count() == 0
    finally:
        db.close()
    if a.seed or empty:  # never wipe a ledger that already has data unless asked to
        print(f"(seeded {seed_db(a.patient)} demo events for {a.patient})")

    llm = DemoLLM() if a.demo else resolve_llm(settings)
    print(f"(LLM: {llm.name})")
    active = [x for x in ("lab", "symptom", "cycle") if x not in {p.strip() for p in a.pause.split(",") if p.strip()}]
    run_id = str(uuid.uuid4())
    runner.register(run_id)
    asyncio.run(runner.run(run_id, a.patient, question, active, llm=llm))

    db = SessionLocal()
    try:
        run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).one()
        status, result, log = run.status, run.result or {}, run.event_log or []
    finally:
        db.close()
    if status != "done":
        print(f"analysis failed: {log[-1].get('message') if log else 'unknown error'}")
        return run_id
    for agent, h in (result.get("hypotheses") or {}).items():
        print(f"\n[{agent}] " + (f"{h['claim']}  (confidence {h['confidence']:.2f}, cites {', '.join(h['evidence_ids']) or 'nothing'})"
                                if h else f"skipped ({(result.get('agent_status') or {}).get(agent)})"))
    disc = result.get("discordance") or {}
    print(f"\nDiscordance: {'conflict' if disc.get('conflict') else 'no conflict'} — "
          + "; ".join(f"{p['a']}×{p['b']}: {p['relation']}" for p in disc.get("pairs", [])))
    for agent, r in sorted((result.get("debate") or {}).items()):
        if r:
            print(f"  {agent}: {r['text']}")
    v = result.get("verdict") or {}
    print(f"\nVerdict: {v.get('headline')}\n{v.get('summary')}\nOverall confidence {v.get('overall_confidence')}")
    print(f"\nsaved analysis {run_id}")
    if a.golden:
        with open(a.golden, "w") as f:
            json.dump({"question": question, "result": result, "event_log": log}, f, ensure_ascii=False, indent=1)
        print(f"wrote replay recording to {a.golden}")
    return run_id


if __name__ == "__main__":
    main()
