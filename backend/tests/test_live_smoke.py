"""Real LLM end-to-end. Deselected by default; run with:  HORMONY_LIVE_TESTS=1 pytest -m live"""
import asyncio
import os

import pytest


@pytest.mark.live
def test_live_end_to_end(seeded):
    if not os.environ.get("HORMONY_LIVE_TESTS"):
        pytest.skip("set HORMONY_LIVE_TESTS=1 (and a provider key) to run")
    from hormony.agents.graph import build_graph
    from hormony.agents.llm import resolve_llm
    from hormony.config import Settings
    llm = resolve_llm(Settings())
    assert llm.name != "demo", "configure HORMONY_LLM / a provider key for the live test"
    out = asyncio.run(build_graph(llm).ainvoke({"patient_id": "nancy", "active_agents": ["lab", "symptom", "cycle"],
                                                "question": "Why have my fatigue episodes increased over the last two cycles?"}))
    assert [k for k, v in out["hypotheses"].items() if v], "every agent was unavailable"
    assert out["verdict"]["headline"]
