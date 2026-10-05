from __future__ import annotations

import asyncio
import json
import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .. import runner
from ..agents.llm import LLMConfigError, resolve_llm
from ..config import settings
from ..db import SessionLocal
from ..models import AnalysisRun

router = APIRouter()
AGENTS = ("lab", "symptom", "cycle")
GOLDEN = os.path.join(os.path.dirname(__file__), "..", "..", "sample_data", "golden_run.json")


class AnalysisIn(BaseModel):
    patient_id: str = Field("nancy", max_length=40)
    question: str = Field(max_length=500)
    active_agents: Optional[List[str]] = None


def _active(v: Optional[List[str]]) -> List[str]:
    return list(AGENTS) if v is None else [a for a in v if a in AGENTS]


def _save(run_id: str, body: AnalysisIn, status: str, result=None, event_log=None) -> None:
    db = SessionLocal()
    try:
        db.add(AnalysisRun(id=run_id, patient_id=body.patient_id, question=body.question, status=status,
                           result=result, event_log=event_log))
        db.commit()
    finally:
        db.close()


def replay_for(golden: dict, active: List[str], run_id: str):
    """The recorded golden run, with paused agents removed the way a live run would remove them."""
    paused = set(AGENTS) - set(active)
    events, result = [], json.loads(json.dumps(golden["result"]))
    for e in golden["event_log"]:
        a, kind = e.get("agent"), e["type"]
        if a in paused and kind in ("thought", "message"):
            continue
        if a in paused and kind == "hypothesis":
            events.append({"type": "agent_skipped", "agent": a, "reason": "paused"})
            continue
        if kind == "discordance":
            pairs = [p for p in e["pairs"] if p["a"] not in paused and p["b"] not in paused]
            e = {**e, "pairs": pairs, "conflict": any(p["relation"] == "conflict" for p in pairs),
                 "active": len(active)}
        if kind == "verdict":
            e = {**e, "adjustments": [x for x in e.get("adjustments", []) if x["agent"] not in paused]}
        if kind == "done":
            e = {"type": "done", "analysis_id": run_id}
        events.append(e)
    if not any(e["type"] == "discordance" and e["conflict"] for e in events):
        events = [e for e in events if e["type"] != "message"]
    for a in paused:
        (result.get("hypotheses") or {})[a] = None
        (result.get("debate") or {}).pop(a, None)
    if result.get("verdict"):
        result["verdict"]["adjustments"] = [x for x in result["verdict"].get("adjustments", []) if x["agent"] not in paused]
    for edge in (result.get("graph") or {}).get("edges", []):
        if edge.get("agent") in paused:
            edge["confidence"] = None
    return events, result


async def _replay(run_id: str, events: List[dict]) -> None:
    for e in events:
        await asyncio.sleep({"thought": 0.25, "message": 0.9}.get(e["type"], 0.05))
        await runner._push(run_id, e)


@router.post("/analyses")
async def create_analysis(body: AnalysisIn):
    active = _active(body.active_agents)
    run_id = str(uuid.uuid4())
    if settings.demo_replay:
        with open(GOLDEN) as f:
            events, result = replay_for(json.load(f), active, run_id)
        _save(run_id, body, "done", result, events)
        entry = runner.register(run_id)
        entry["task"] = asyncio.create_task(_replay(run_id, events))
        return {"id": run_id}
    try:
        llm = resolve_llm(settings)
    except LLMConfigError as e:
        raise HTTPException(503, f"LLM misconfigured: {e}")
    _save(run_id, body, "running")
    entry = runner.register(run_id)
    entry["task"] = asyncio.create_task(runner.run(run_id, body.patient_id, body.question, active, llm=llm))
    return {"id": run_id}


@router.get("/analyses/{run_id}/stream")
async def stream(run_id: str):
    async def gen():
        async for evt in runner.follow(run_id):
            yield f"data: {json.dumps(evt)}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/analyses/{run_id}")
async def get_analysis(run_id: str):
    db = SessionLocal()
    try:
        ar = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
    finally:
        db.close()
    if not ar:
        raise HTTPException(404, "unknown analysis")
    r = ar.result or {}
    return {"question": ar.question, "status": ar.status,
            **{k: r.get(k) for k in ("facts", "hypotheses", "agent_status", "discordance", "debate",
                                     "verdict", "report", "graph", "brief")}}
