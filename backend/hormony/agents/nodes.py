from __future__ import annotations

import asyncio
from typing import Dict, List, Optional

from ..analysis.features import analyze
from ..ledger.store import load_ledger
from ..outputs.hypothesis_graph import build as build_graph_out
from ..outputs.report import build as build_report, build_brief
from . import prompts
from .discordance import compare
from .llm import AgentUnavailable
from .provenance import guard
from .schemas import Fact, Hypothesis, Rebuttal, Verdict

AGENTS = ("lab", "symptom", "cycle")


def _facts(state: dict, group: str) -> List[Fact]:
    return [Fact(**f) if isinstance(f, dict) else f for f in (state.get("facts") or {}).get(group, [])]


def _hyps(state: dict) -> Dict[str, Optional[Hypothesis]]:
    return {k: (Hypothesis(**v) if isinstance(v, dict) else v) for k, v in (state.get("hypotheses") or {}).items()}


def _rebuttals(state: dict) -> Dict[str, Optional[Rebuttal]]:
    return {k: (Rebuttal(**v) if isinstance(v, dict) else v) for k, v in (state.get("rebuttals") or {}).items()}


async def scope(state: dict) -> dict:
    events, starts, today = load_ledger(state["patient_id"])
    facts, stats = analyze(events, starts, today)
    return {"facts": {k: [f.model_dump() for f in v] for k, v in facts.items()},
            "stats": stats, "ledger_ids": [e.id for e in events]}


def make_specialist(name: str, llm):
    async def run(state: dict) -> dict:
        if name not in state.get("active_agents", list(AGENTS)):
            return {"hypotheses": {name: None}, "agent_status": {name: "paused"}}
        try:
            hyp = await llm.structured(prompts.specialist_system(name),
                                       prompts.specialist_user(state.get("question", ""), _facts(state, name)),
                                       Hypothesis, effort="low")
        except AgentUnavailable:
            return {"hypotheses": {name: None}, "agent_status": {name: "unavailable"}}
        hyp = guard(hyp, state.get("ledger_ids", []))
        return {"hypotheses": {name: hyp.model_dump()}, "agent_status": {name: "ok"}}
    return run


async def discordance(state: dict) -> dict:
    return {"discordance": compare(_hyps(state))}


def make_debate(llm):
    async def run(state: dict) -> dict:
        live = {k: h for k, h in _hyps(state).items() if h is not None}
        allowed = set(state.get("ledger_ids", []))

        async def one(agent: str):
            others = [(k, h.claim) for k, h in live.items() if k != agent]
            try:
                reb = await llm.structured(
                    prompts.debate_system(agent),
                    prompts.debate_user(state.get("question", ""), live[agent].claim, live[agent].confidence,
                                        _facts(state, agent), others),
                    Rebuttal, effort="low")
            except AgentUnavailable:
                return agent, None
            data = reb.model_dump()
            data["evidence_ids"] = [i for i in data.get("evidence_ids", []) if i in allowed]
            return agent, data

        return {"rebuttals": dict(await asyncio.gather(*[one(a) for a in live]))}
    return run


def make_critic(llm):
    async def run(state: dict) -> dict:
        hyps, rebs = _hyps(state), _rebuttals(state)
        payload = {
            "focus": ((state.get("stats") or {}).get("focus") or {}).get("name"),
            "hypotheses": {k: (h.model_dump() if h else None) for k, h in hyps.items()},
            "agent_status": state.get("agent_status") or {},
            "rebuttals": {k: (r.model_dump() if r else None) for k, r in rebs.items()},
            "discordance": state.get("discordance") or {},
            "shared_facts": [f.model_dump() for f in _facts(state, "shared")],
        }
        try:
            verdict = await llm.structured(prompts.critic_system(),
                                           prompts.critic_user(state.get("question", ""), payload), Verdict, effort="high")
        except AgentUnavailable:
            # keep every hypothesis and its own confidence; say plainly that no review happened
            verdict = Verdict(single_cause_supported=False,
                              headline="The specialists' hypotheses are shown without a critic review.",
                              summary="The reasoning critic was unavailable, so each hypothesis keeps its original confidence.",
                              unassigned_factors=[f.statement for f in _facts(state, "shared")],
                              overall_confidence=round(min([h.confidence for h in hyps.values() if h] or [0.2]), 2))
        return {"verdict": verdict.model_dump()}
    return run


async def report(state: dict) -> dict:
    facts = {k: _facts(state, k) for k in (state.get("facts") or {})}
    verdict = Verdict(**state["verdict"])
    stats = state.get("stats") or {}
    hyps = _hyps(state)
    return {"report": {"report": build_report(facts, hyps, verdict, stats),
                       "graph": build_graph_out(stats, verdict, hyps),
                       "brief": build_brief(verdict, stats)}}
