"""Runs one analysis graph exactly once and turns its progress into the SSE event log.

The graph is streamed with stream_mode=["updates", "values"]: "updates" drive the live events, and
the last "values" chunk is the final state that gets saved, so the saved result is always the run
the user watched.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Dict, List

from .agents.graph import build_graph
from .agents.llm import resolve_llm
from .config import settings
from .db import SessionLocal
from .models import AnalysisRun

log = logging.getLogger("hormony.runner")

RUNS: Dict[str, dict] = {}
MAX_RUNS = 50
THOUGHT_DELAY = 0.25
AGENTS = ("lab", "symptom", "cycle")
STEP_LABELS = ["Scoping your evidence ledger", "Specialists analyzing independently",
               "Discordance engine comparing conclusions", "Agents debating the evidence", "Reasoning critic reviewing"]


def new_entry() -> dict:
    return {"events": [], "done": False, "cond": asyncio.Condition(), "task": None}


def register(run_id: str) -> dict:
    """Track a live run; forget the oldest finished runs (they replay from the database)."""
    finished = [k for k, v in RUNS.items() if v["done"]]
    for k in finished[: max(0, len(RUNS) - MAX_RUNS + 1)]:
        RUNS.pop(k, None)
    RUNS[run_id] = new_entry()
    return RUNS[run_id]


def get_llm():
    return resolve_llm(settings)


async def _push(run_id: str, evt: dict) -> None:
    entry = RUNS.get(run_id)
    if not entry:
        return
    async with entry["cond"]:
        entry["events"].append(evt)
        if evt.get("type") in ("done", "error"):
            entry["done"] = True
        entry["cond"].notify_all()


def _persist(run_id: str, patient_id: str, question: str, status: str, result, event_log: List[dict]) -> None:
    db = SessionLocal()
    try:
        ar = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
        if ar is None:
            ar = AnalysisRun(id=run_id, patient_id=patient_id, question=question)
            db.add(ar)
        ar.status, ar.result, ar.event_log = status, result, event_log
        db.commit()
    finally:
        db.close()


def build_result(question: str, final: dict) -> dict:
    outputs = final.get("report") or {}
    return {"question": question, "facts": final.get("facts"), "stats": final.get("stats"),
            "hypotheses": final.get("hypotheses"), "agent_status": final.get("agent_status"),
            "discordance": final.get("discordance"), "debate": final.get("rebuttals") or {},
            "verdict": final.get("verdict"), "report": outputs.get("report"),
            "graph": outputs.get("graph"), "brief": outputs.get("brief")}


async def run(run_id: str, patient_id: str, question: str, active_agents: List[str], llm=None) -> None:
    if run_id not in RUNS:
        register(run_id)
    thoughts: Dict[str, asyncio.Task] = {}
    steps: set = set()

    async def step(i: int, **extra):
        if i not in steps:
            steps.add(i)
            await _push(run_id, {"type": "step", "index": i, "label": STEP_LABELS[i], **extra})

    async def stream_thoughts(agent: str, facts: List[dict]):
        for f in facts[:3]:
            await _push(run_id, {"type": "thought", "agent": agent, "text": f["statement"]})
            await asyncio.sleep(THOUGHT_DELAY)

    try:
        llm = llm or get_llm()
        await step(0, llm=getattr(llm, "name", "unknown"))
        final: dict = {}
        state = {"patient_id": patient_id, "question": question, "active_agents": list(active_agents)}
        async for mode, chunk in build_graph(llm).astream(state, stream_mode=["updates", "values"]):
            if mode == "values":
                final = chunk
                continue
            for node, payload in chunk.items():
                payload = payload or {}
                if node == "scope":
                    await _push(run_id, {"type": "ledger", "counts": (payload.get("stats") or {}).get("counts", {})})
                    await step(1)
                    for agent in AGENTS:  # never stream a paused agent's facts
                        if agent in active_agents:
                            facts = (payload.get("facts") or {}).get(agent, [])
                            thoughts[agent] = asyncio.create_task(stream_thoughts(agent, facts))
                elif node.endswith("_agent"):
                    agent = node[: -len("_agent")]
                    if agent in thoughts:
                        await thoughts[agent]  # an agent's thoughts always precede its hypothesis
                    h = (payload.get("hypotheses") or {}).get(agent)
                    if h:
                        await _push(run_id, {"type": "hypothesis", "agent": agent, "claim": h["claim"],
                                             "leading_factor": h["leading_factor"], "confidence": h["confidence"],
                                             "evidence_ids": h.get("evidence_ids", [])})
                    else:
                        reason = (payload.get("agent_status") or {}).get(agent, "unavailable")
                        await _push(run_id, {"type": "agent_skipped", "agent": agent, "reason": reason})
                elif node == "discordance":
                    await step(2)
                    await _push(run_id, {"type": "discordance", **(payload.get("discordance") or {})})
                elif node == "debate":
                    await step(3)
                    for agent, reb in sorted((payload.get("rebuttals") or {}).items()):
                        if reb:
                            await _push(run_id, {"type": "message", "agent": agent, "text": reb["text"],
                                                 "evidence_ids": reb.get("evidence_ids", []),
                                                 "revised_confidence": reb.get("revised_confidence")})
                elif node == "critic":
                    if 3 not in steps:
                        steps.add(3)
                        await _push(run_id, {"type": "step", "index": 3, "label": "No conflict, so no debate was needed"})
                    await step(4)
                    await _push(run_id, {"type": "verdict", **(payload.get("verdict") or {})})
        done = {"type": "done", "analysis_id": run_id}
        # save first, then announce: a client that reacts to `done` can fetch the full result immediately
        _persist(run_id, patient_id, question, "done", build_result(question, final), RUNS[run_id]["events"] + [done])
        await _push(run_id, done)
    except Exception as ex:  # noqa: BLE001 - every failure must end the stream with an error event
        log.exception("analysis %s failed", run_id)
        for t in thoughts.values():
            t.cancel()
        err = {"type": "error", "message": f"{type(ex).__name__}: {ex}"[:300]}
        try:
            _persist(run_id, patient_id, question, "error", None, RUNS[run_id]["events"] + [err])
        finally:
            await _push(run_id, err)


async def follow(run_id: str):
    """Replay a run's events, then tail it live until done/error. Never yields while holding the lock."""
    entry = RUNS.get(run_id)
    if entry is None:
        db = SessionLocal()
        try:
            ar = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
        finally:
            db.close()
        if not ar:
            yield {"type": "error", "message": "unknown analysis"}
            return
        events = list(ar.event_log or [])
        if not events or events[-1].get("type") not in ("done", "error"):
            events.append({"type": "done", "analysis_id": run_id} if ar.status == "done" else
                          {"type": "error", "message": "This analysis was interrupted (the server restarted). Please run it again."})
        for e in events:
            yield e
        return
    idx = 0
    while True:
        async with entry["cond"]:
            while idx >= len(entry["events"]) and not entry["done"]:
                try:
                    await asyncio.wait_for(entry["cond"].wait(), timeout=30)
                except asyncio.TimeoutError:
                    pass
            batch = entry["events"][idx:]
            idx += len(batch)
            finished = entry["done"]
        for e in batch:
            yield e
            if e.get("type") in ("done", "error"):
                return
        if finished and idx >= len(entry["events"]):
            return
