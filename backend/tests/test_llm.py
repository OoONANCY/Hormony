"""LLM providers: explicit selection, Anthropic error mapping, OpenRouter (Nemotron) adapter, data-driven demo."""
import asyncio
import json
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from hormony.agents.llm import (
    AgentUnavailable, AnthropicLLM, DemoLLM, LLMConfigError, OpenRouterLLM, resolve_llm,
)
from hormony.agents.schemas import Hypothesis, Rebuttal, Verdict
from hormony.config import Settings


def run(coro):
    return asyncio.run(coro)


# ---------------- provider selection ----------------

def test_explicit_provider_wins():
    assert isinstance(resolve_llm(Settings(llm="demo", openrouter_api_key="k")), DemoLLM)


def test_auto_picks_openrouter_when_its_key_is_set():
    llm = resolve_llm(Settings(llm="", openrouter_api_key="or-key"))
    assert isinstance(llm, OpenRouterLLM)
    assert llm.name == "openrouter:nvidia/nemotron-3-super-120b-a12b:free"


def test_auto_picks_anthropic_when_its_key_is_set():
    llm = resolve_llm(Settings(llm="", anthropic_api_key="sk-ant-test"))
    assert isinstance(llm, AnthropicLLM)
    assert llm.client.api_key == "sk-ant-test"


def test_auto_without_keys_is_demo():
    assert resolve_llm(Settings(llm="")).name == "demo"


def test_misconfigured_provider_fails_loudly():
    with pytest.raises(LLMConfigError):
        resolve_llm(Settings(llm="openrouter", openrouter_api_key=""))
    with pytest.raises(LLMConfigError):
        resolve_llm(Settings(llm="gpt-whatever"))


def test_settings_read_standard_key_names_from_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv("HORMONY_LLM", raising=False)  # real env vars rightly take priority over .env
    env = tmp_path / ".env"
    env.write_text("ANTHROPIC_API_KEY=sk-a\nOPENROUTER_API_KEY=sk-or\nHORMONY_LLM=openrouter\n")
    s = Settings(_env_file=str(env))
    assert (s.anthropic_api_key, s.openrouter_api_key, s.llm) == ("sk-a", "sk-or", "openrouter")


# ---------------- Anthropic error mapping ----------------

def _anthropic_with(behaviour):
    llm = AnthropicLLM(api_key="sk-test")

    async def parse(**kwargs):
        return behaviour(kwargs)
    llm.client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(parse=parse)))
    return llm


def _status_error(cls, code):
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    try:
        import httpx2
        req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
        resp = httpx2.Response(code, request=req)
    except ImportError:  # pragma: no cover
        resp = httpx.Response(code, request=req)
    return cls(f"status {code}", response=resp, body=None)


def test_anthropic_overloaded_marks_agent_unavailable():
    def boom(_):
        raise _status_error(anthropic.OverloadedError, 529)
    with pytest.raises(AgentUnavailable):
        run(_anthropic_with(boom).structured("s", "u", Hypothesis))


def test_anthropic_truncated_output_marks_agent_unavailable():
    llm = _anthropic_with(lambda _: SimpleNamespace(stop_reason="max_tokens", parsed_output=None))
    with pytest.raises(AgentUnavailable):
        run(llm.structured("s", "u", Hypothesis))


def test_anthropic_auth_error_propagates():
    def boom(_):
        raise _status_error(anthropic.AuthenticationError, 401)
    with pytest.raises(anthropic.AuthenticationError):
        run(_anthropic_with(boom).structured("s", "u", Hypothesis))


# ---------------- OpenRouter (Nemotron) ----------------

HYP = {"claim": "Fatigue is associated with late-cycle days.", "leading_factor": "cycle_timing",
       "confidence": 0.7, "evidence_ids": ["SYM-0926-F"], "caveats": []}


def _chat(content, finish="stop"):
    return {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": finish}]}


def _router(responses):
    """MockTransport that replays `responses` (callables or (status, json)) and records requests."""
    seen = []

    def handler(request: httpx.Request):
        seen.append(json.loads(request.content))
        r = responses[min(len(seen) - 1, len(responses) - 1)]
        status, body = r
        return httpx.Response(status, json=body)
    return seen, httpx.MockTransport(handler)


def _or(responses, **kw):
    seen, transport = _router(responses)
    llm = OpenRouterLLM(api_key="sk-or", model=kw.get("model", "nvidia/nemotron-3-super-120b-a12b:free"),
                        transport=transport, retry_delay=0)
    return seen, llm


def test_openrouter_requests_strict_json_schema_and_parses_it():
    seen, llm = _or([(200, _chat(json.dumps(HYP)))])
    out = run(llm.structured("[agent:cycle] sys", "facts", Hypothesis, effort="low"))
    assert out.leading_factor == "cycle_timing"
    body = seen[0]
    assert body["model"] == "nvidia/nemotron-3-super-120b-a12b:free"
    rf = body["response_format"]
    assert rf["type"] == "json_schema" and rf["json_schema"]["strict"] is True
    schema = rf["json_schema"]["schema"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])


def test_openrouter_extracts_json_after_reasoning_text():
    content = "<think>check the facts first</think>\n```json\n" + json.dumps(HYP) + "\n```"
    _, llm = _or([(200, _chat(content))])
    assert run(llm.structured("s", "u", Hypothesis)).confidence == 0.7


def test_openrouter_falls_back_when_model_lacks_json_schema_support():
    seen, llm = _or([(400, {"error": {"message": "response_format json_schema is not supported"}}),
                     (200, _chat(json.dumps(HYP)))])
    run(llm.structured("s", "u", Hypothesis))
    assert "response_format" in seen[0] and "response_format" not in seen[1]
    assert "JSON" in seen[1]["messages"][0]["content"]  # schema moved into the instructions


def test_openrouter_repairs_one_invalid_answer():
    bad = dict(HYP)
    del bad["leading_factor"]
    seen, llm = _or([(200, _chat(json.dumps(bad))), (200, _chat(json.dumps(HYP)))])
    assert run(llm.structured("s", "u", Hypothesis)).leading_factor == "cycle_timing"
    assert len(seen) == 2 and "leading_factor" in seen[1]["messages"][-1]["content"]


def test_openrouter_rate_limit_retries_then_marks_unavailable():
    seen, llm = _or([(429, {"error": {"message": "rate limited"}})])
    with pytest.raises(AgentUnavailable):
        run(llm.structured("s", "u", Hypothesis))
    assert len(seen) == 3


def test_openrouter_bad_key_is_a_config_error():
    _, llm = _or([(401, {"error": {"message": "No auth credentials found"}})])
    with pytest.raises(LLMConfigError):
        run(llm.structured("s", "u", Hypothesis))


# ---------------- demo engine is driven by the facts it is given ----------------

LAB_PROMPT = ("Question: Why fatigue?\nFacts:\n"
              "- (F-LAB-2) Day-21 progesterone 9.9 ng/mL on Aug 1 → 3.1 ng/mL on Sep 26 [IDs: LAB-0801-P4, LAB-0926-P4]\n")


def test_demo_hypothesis_is_built_from_the_prompt_facts():
    h = run(DemoLLM().structured("[agent:lab] sys", LAB_PROMPT, Hypothesis))
    assert "9.9" in h.claim and "3.1" in h.claim
    assert h.evidence_ids == ["LAB-0801-P4", "LAB-0926-P4"]
    assert h.leading_factor == "lab_change"


def test_demo_hypothesis_without_facts_is_insufficient_data():
    h = run(DemoLLM().structured("[agent:lab] sys", "Question: q\nFacts:\n", Hypothesis))
    assert h.leading_factor == "insufficient_data" and h.evidence_ids == []


def test_demo_verdict_is_built_from_hypotheses_in_the_prompt():
    payload = {"hypotheses": {"cycle": {"claim": "c", "leading_factor": "cycle_timing", "confidence": 0.65, "evidence_ids": ["CYC-0809"]},
                              "symptom": {"claim": "s", "leading_factor": "medication", "confidence": 0.71, "evidence_ids": ["MED-0816"]}},
               "rebuttals": {"cycle": {"text": "t", "evidence_ids": [], "revised_confidence": 0.74},
                             "symptom": {"text": "t", "evidence_ids": [], "revised_confidence": 0.6}},
               "shared_facts": [{"id": "F-SHARED-1", "statement": "On comparable nights sleep 7.1 h → 6.8 h", "evidence_ids": []}]}
    v = run(DemoLLM().structured("[critic] sys", "Question: q\nINPUT_JSON:" + json.dumps(payload), Verdict))
    assert {a.agent: a.after for a in v.adjustments} == {"cycle": 0.74, "symptom": 0.6}
    assert v.ranked_factors[0] == "cycle_timing"
    assert any("6.8" in u for u in v.unassigned_factors)


def test_demo_rebuttal_cites_its_own_facts():
    user = ("Question: q\nYour hypothesis (confidence 0.78): lab claim\nYour facts:\n"
            "- (F-LAB-2) Day-21 progesterone 7.9 ng/mL on Aug 1 → 4.2 ng/mL on Sep 26 [IDs: LAB-0801-P4, LAB-0926-P4]\n"
            "Other agents:\n- symptom: s\n")
    r = run(DemoLLM().structured("[debate:lab] sys", user, Rebuttal))
    assert r.evidence_ids == ["LAB-0801-P4", "LAB-0926-P4"]
    assert r.revised_confidence < 0.78  # only two comparable samples
