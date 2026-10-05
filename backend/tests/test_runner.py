"""Runner: single graph execution, honest event stream, durable event log, non-blocking followers."""
import asyncio
import uuid

from hormony import runner
from hormony.agents.llm import DemoLLM, AgentUnavailable
from hormony.db import SessionLocal
from hormony.models import AnalysisRun


class CountingLLM(DemoLLM):
    """Demo engine that counts calls and stamps each call number into free text."""

    def __init__(self, fail_marker: str | None = None, unavailable_marker: str | None = None):
        self.calls: list[str] = []
        self.fail_marker = fail_marker
        self.unavailable_marker = unavailable_marker

    async def structured(self, system, user, schema, effort="medium"):
        self.calls.append(system.split("]")[0] + "]")
        if self.unavailable_marker and self.unavailable_marker in system:
            raise AgentUnavailable("test: unavailable")
        if self.fail_marker and self.fail_marker in system:
            raise RuntimeError("test: node crashed")
        out = await super().structured(system, user, schema, effort)
        n = len(self.calls)
        if hasattr(out, "claim"):
            out.claim = f"{out.claim} [call {n}]"
        if hasattr(out, "summary"):
            out.summary = f"{out.summary} [call {n}]"
        return out


def _new_run(question="Why have my fatigue episodes increased?", patient="nancy"):
    rid = str(uuid.uuid4())
    db = SessionLocal()
    db.add(AnalysisRun(id=rid, patient_id=patient, question=question, status="running"))
    db.commit()
    db.close()
    runner.RUNS[rid] = runner.new_entry()
    return rid


def _run(rid, llm, active=("lab", "symptom", "cycle"), patient="nancy", q="Why fatigue?"):
    asyncio.run(runner.run(rid, patient, q, list(active), llm=llm))
    return runner.RUNS[rid]["events"]


def _saved(rid):
    db = SessionLocal()
    try:
        return db.query(AnalysisRun).filter(AnalysisRun.id == rid).one()
    finally:
        db.close()


def test_analysis_runs_the_graph_exactly_once(seeded):
    llm = CountingLLM()
    _run(_new_run(), llm)
    # 3 specialists + 3 rebuttals (the demo data has a conflict) + 1 critic
    assert len(llm.calls) == 7, llm.calls


def test_saved_result_is_the_streamed_run(seeded):
    rid = _new_run()
    events = _run(rid, CountingLLM())
    streamed = {e["agent"]: e["claim"] for e in events if e["type"] == "hypothesis"}
    verdict = [e for e in events if e["type"] == "verdict"][0]
    saved = _saved(rid).result
    assert {k: v["claim"] for k, v in saved["hypotheses"].items() if v} == streamed
    assert saved["verdict"]["summary"] == verdict["summary"]


def test_persisted_event_log_ends_with_done_and_replays_after_restart(seeded):
    rid = _new_run()
    _run(rid, CountingLLM())
    run = _saved(rid)
    assert run.status == "done"
    assert run.event_log[-1]["type"] == "done"
    assert run.result["report"] and run.result["graph"] and run.result["brief"]
    runner.RUNS.clear()  # simulate a server restart

    async def replay():
        return [e async for e in runner.follow(rid)]
    replayed = asyncio.run(replay())
    assert replayed[-1]["type"] == "done"
    assert [e["type"] for e in replayed] == [e["type"] for e in run.event_log]


def test_failed_run_persists_its_log_with_an_error_event(seeded):
    rid = _new_run()
    events = _run(rid, CountingLLM(fail_marker="[critic]"))
    assert events[-1]["type"] == "error"
    run = _saved(rid)
    assert run.status == "error"
    assert run.event_log and run.event_log[-1]["type"] == "error"


def test_paused_agent_streams_no_facts_and_is_skipped_as_paused(seeded):
    events = _run(_new_run(), CountingLLM(), active=("symptom", "cycle"))
    assert not [e for e in events if e["type"] == "thought" and e["agent"] == "lab"]
    skipped = [e for e in events if e["type"] == "agent_skipped"]
    assert skipped == [{"type": "agent_skipped", "agent": "lab", "reason": "paused"}]


def test_unavailable_agent_is_reported_as_unavailable(seeded):
    events = _run(_new_run(), CountingLLM(unavailable_marker="[agent:lab]"))
    skipped = [e for e in events if e["type"] == "agent_skipped"]
    assert skipped == [{"type": "agent_skipped", "agent": "lab", "reason": "unavailable"}]
    assert events[-1]["type"] == "done"


def test_thoughts_for_an_agent_arrive_before_its_hypothesis(seeded):
    events = _run(_new_run(), CountingLLM())
    for agent in ("lab", "symptom", "cycle"):
        idx = [i for i, e in enumerate(events) if e.get("agent") == agent]
        kinds = [events[i]["type"] for i in idx]
        assert "hypothesis" in kinds
        assert kinds.index("hypothesis") > max(i for i, k in enumerate(kinds) if k == "thought")


def test_all_five_steps_are_emitted_and_step0_names_the_llm(seeded):
    events = _run(_new_run(), CountingLLM())
    steps = [e for e in events if e["type"] == "step"]
    assert [s["index"] for s in steps] == [0, 1, 2, 3, 4]
    assert steps[0]["llm"] == "demo"


def test_discordance_pairs_carry_a_note(seeded):
    events = _run(_new_run(), CountingLLM())
    disc = [e for e in events if e["type"] == "discordance"][0]
    assert disc["pairs"] and all(p.get("note") for p in disc["pairs"])


def test_analysis_uses_the_requested_patient(seeded):
    rid = _new_run(patient="ghost")
    events = _run(rid, CountingLLM(), patient="ghost")
    ledger = [e for e in events if e["type"] == "ledger"][0]
    assert sum(ledger["counts"].values()) == 0
    for e in events:
        assert not [i for i in e.get("evidence_ids", []) if i.startswith(("LAB-", "SYM-", "MED-", "CYC-"))]


def test_a_stalled_follower_does_not_block_the_run():
    rid = str(uuid.uuid4())
    runner.RUNS[rid] = runner.new_entry()

    async def scenario():
        agen = runner.follow(rid)
        await runner._push(rid, {"type": "step", "index": 0})
        first = await agen.__anext__()          # follower now suspended at `yield`
        assert first["type"] == "step"

        async def push_more():
            for i in range(5):
                await runner._push(rid, {"type": "thought", "agent": "lab", "text": str(i)})
        await asyncio.wait_for(push_more(), timeout=1.0)
        await agen.aclose()
    asyncio.run(scenario())
