"""LLM providers behind one interface: `await llm.structured(system, user, PydanticModel, effort)`.

- AnthropicLLM   Claude via the official SDK (structured outputs, server-side refusal fallback).
- OpenRouterLLM  any OpenRouter model, e.g. NVIDIA Nemotron (strict JSON schema when the model
                 supports it, otherwise schema-in-prompt + validation + one repair turn).
- DemoLLM        offline, deterministic, no network; it composes its text from the facts it is
                 given, so its numbers always match the data.

`resolve_llm(settings)` picks the provider. A misconfigured provider raises LLMConfigError; it
is never silently replaced by the demo engine.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any, List, Optional, Protocol, Tuple, TypeVar

from pydantic import BaseModel, ValidationError

from ..config import Settings, settings as default_settings

T = TypeVar("T", bound=BaseModel)


class AgentUnavailable(Exception):
    """A transient or content problem for one call; that agent is marked unavailable and the run continues."""


class LLMConfigError(Exception):
    """The configured provider cannot work (missing/invalid key, unknown provider). Fails the request loudly."""


class LLM(Protocol):
    name: str

    async def structured(self, system: str, user: str, schema: type[T], effort: str = "medium") -> T: ...


# ---------------------------------------------------------------- selection

def provider_name(cfg: Settings) -> str:
    """Which provider `resolve_llm` would build, without building it (used by /health)."""
    choice = (cfg.llm or "").strip().lower()
    if not choice:
        if cfg.openrouter_api_key:
            choice = "openrouter"
        elif cfg.anthropic_api_key or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
            choice = "anthropic"
        else:
            choice = "demo"
    if choice == "demo":
        return "demo"
    if choice == "openrouter":
        if not cfg.openrouter_api_key:
            raise LLMConfigError("HORMONY_LLM=openrouter needs OPENROUTER_API_KEY (or HORMONY_OPENROUTER_API_KEY) in backend/.env")
        return f"openrouter:{cfg.openrouter_model}"
    if choice == "anthropic":
        return f"anthropic:{cfg.model}"
    raise LLMConfigError(f"Unknown HORMONY_LLM={cfg.llm!r}; use demo, anthropic or openrouter")


def resolve_llm(cfg: Optional[Settings] = None) -> "LLM":
    cfg = cfg or default_settings
    name = provider_name(cfg)
    if name == "demo":
        return DemoLLM()
    if name.startswith("openrouter:"):
        return OpenRouterLLM(api_key=cfg.openrouter_api_key, model=cfg.openrouter_model)
    try:  # no key configured -> the SDK resolves ANTHROPIC_AUTH_TOKEN or an `ant auth login` profile
        return AnthropicLLM(api_key=cfg.anthropic_api_key or None, model=cfg.model)
    except Exception as e:
        raise LLMConfigError(f"Anthropic client could not be created: {e}") from e


# ---------------------------------------------------------------- Anthropic

class AnthropicLLM:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        import anthropic
        self._anthropic = anthropic
        self.model = model or default_settings.model
        self.name = f"anthropic:{self.model}"
        self.client = anthropic.AsyncAnthropic(api_key=api_key) if api_key else anthropic.AsyncAnthropic()

    async def structured(self, system, user, schema, effort="medium"):
        a = self._anthropic
        # The SDK already retried these; if they persist, only this agent is affected.
        transient = tuple(c for c in (a.RateLimitError, getattr(a, "OverloadedError", None),
                                      a.InternalServerError, a.APIConnectionError) if c)
        try:
            response = await self.client.beta.messages.parse(
                model=self.model,
                max_tokens=16000,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=schema,
                output_config={"effort": effort},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except transient as e:
            raise AgentUnavailable(f"{type(e).__name__}: {e}") from e
        except ValidationError as e:
            raise AgentUnavailable(f"output did not match {schema.__name__}: {e.errors()[:1]}") from e
        stop = getattr(response, "stop_reason", None)
        if stop == "refusal":
            raise AgentUnavailable("declined")
        parsed = getattr(response, "parsed_output", None)
        if stop == "max_tokens" or parsed is None:
            raise AgentUnavailable(f"incomplete output (stop_reason={stop})")
        return parsed


# ---------------------------------------------------------------- OpenRouter

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_DROP = ("title", "default", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "minLength", "maxLength")


def strict_schema(model: type[BaseModel]) -> dict:
    """Pydantic JSON schema -> strict structured-output form (closed objects, every property required)."""
    schema = model.model_json_schema()

    def walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        for k in _DROP:
            node.pop(k, None)
        if "properties" in node:
            node["additionalProperties"] = False
            node["required"] = list(node["properties"])
            for v in node["properties"].values():
                walk(v)
        if "items" in node:
            walk(node["items"])
        for k in ("anyOf", "allOf", "oneOf"):
            for v in node.get(k, []):
                walk(v)
        for v in node.get("$defs", {}).values():
            walk(v)

    walk(schema)
    return schema


def extract_json(text: str) -> Any:
    """First JSON object in a reply that may contain reasoning, prose or ``` fences."""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    dec = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch == "{":
            try:
                return dec.raw_decode(text[i:])[0]
            except json.JSONDecodeError:
                continue
    raise ValueError("no JSON object found in the answer")


def _why(e: Exception) -> str:
    if isinstance(e, ValidationError):
        return "; ".join(f"{'.'.join(map(str, err['loc'])) or 'root'}: {err['msg']}" for err in e.errors()[:5])
    return str(e)


class OpenRouterLLM:
    def __init__(self, api_key: str, model: str, transport=None, retry_delay: float = 1.5,
                 timeout: float = 120.0, base_url: str = OPENROUTER_URL) -> None:
        import httpx
        self._httpx = httpx
        self.model = model
        self.name = f"openrouter:{model}"
        self.url = base_url
        self.retry_delay = retry_delay
        self._schema_ok = True  # flips off the first time this model rejects json_schema output
        self.client = httpx.AsyncClient(transport=transport, timeout=timeout, headers={
            "Authorization": f"Bearer {api_key}", "X-Title": "Hormony", "HTTP-Referer": "https://hormony.app"})

    async def structured(self, system, user, schema, effort="medium"):
        js = strict_schema(schema)
        messages = [{"role": "system", "content": f"{system}\n\nRespond with ONLY one JSON object (no prose, no markdown) "
                                                  f"that matches this JSON Schema:\n{json.dumps(js)}"},
                    {"role": "user", "content": user}]
        answer = await self._complete(messages, schema, js, effort)
        try:
            return schema.model_validate(extract_json(answer))
        except (ValueError, ValidationError) as e:  # one repair turn
            messages += [{"role": "assistant", "content": answer},
                         {"role": "user", "content": f"That answer did not match the required JSON schema ({_why(e)}). "
                                                     "Reply with only the corrected JSON object."}]
        answer = await self._complete(messages, schema, js, effort)
        try:
            return schema.model_validate(extract_json(answer))
        except (ValueError, ValidationError) as e:
            raise AgentUnavailable(f"{self.model} returned invalid {schema.__name__}: {_why(e)}") from e

    async def _complete(self, messages, schema, js, effort) -> str:
        body: dict = {"model": self.model, "messages": messages, "max_tokens": 6000, "temperature": 0.2,
                      "reasoning": {"effort": effort if effort in ("low", "medium", "high") else "medium", "exclude": True}}
        if self._schema_ok:
            body["response_format"] = {"type": "json_schema",
                                       "json_schema": {"name": schema.__name__, "strict": True, "schema": js}}
        attempt = 0
        while True:
            attempt += 1
            try:
                r = await self.client.post(self.url, json=body)
            except self._httpx.HTTPError as e:
                if attempt >= 3:
                    raise AgentUnavailable(f"OpenRouter unreachable: {e}") from e
                await asyncio.sleep(self.retry_delay * attempt)
                continue
            err = self._error_text(r)
            if r.status_code in (401, 402, 403):
                raise LLMConfigError(f"OpenRouter rejected the request ({r.status_code}): {err}. "
                                     "Check OPENROUTER_API_KEY / credits / HORMONY_OPENROUTER_MODEL.")
            if r.status_code == 400 and "response_format" in body and re.search(r"response_format|json_schema|structured", err, re.I):
                self._schema_ok = False          # this model can't do strict JSON; keep the schema in the prompt
                body.pop("response_format")
                continue
            if r.status_code in (408, 429) or r.status_code >= 500:
                if attempt >= 3:
                    raise AgentUnavailable(f"OpenRouter {r.status_code}: {err}")
                await asyncio.sleep(self.retry_delay * attempt)
                continue
            if r.status_code != 200:
                raise AgentUnavailable(f"OpenRouter {r.status_code}: {err}")
            data = r.json()
            if data.get("error"):               # upstream provider errors can arrive with HTTP 200
                if attempt >= 3:
                    raise AgentUnavailable(f"OpenRouter provider error: {data['error']}")
                await asyncio.sleep(self.retry_delay * attempt)
                continue
            msg = ((data.get("choices") or [{}])[0].get("message") or {})
            content = msg.get("content") or ""
            if isinstance(content, list):
                content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
            return content

    @staticmethod
    def _error_text(r) -> str:
        try:
            e = r.json().get("error")
            return (e.get("message") if isinstance(e, dict) else str(e)) or r.text[:200]
        except Exception:
            return r.text[:200]


# ---------------------------------------------------------------- Demo (offline)

_FACT = re.compile(r"^- \((?P<id>[^)]+)\) (?P<st>.*?) \[IDs: (?P<ids>[^\]]*)\]\s*$", re.M)
_PHRASE = {"cycle_timing": "your cycle", "medication": "the medication change", "lab_change": "a lab change",
           "sleep": "shorter sleep", "other": "other logged factors", "insufficient_data": "too little data"}
_AGENT_NAME = {"lab": "Lab Agent", "symptom": "Symptom Agent", "cycle": "Cycle Agent"}


def _facts(text: str) -> List[Tuple[str, str, List[str]]]:
    return [(m["id"], m["st"], [i.strip() for i in m["ids"].split(",") if i.strip() and i.strip() != "none"])
            for m in _FACT.finditer(text or "")]


def _marker(system: str) -> Tuple[str, str]:
    m = re.match(r"\[(agent|debate|critic):?([a-z]*)\]", system or "")
    return (m.group(1), m.group(2)) if m else ("", "")


def _ints(s: str) -> List[int]:
    return [int(x) for x in re.findall(r"\b\d+\b", s)]


class DemoLLM:
    """Rule-based stand-in for an LLM: deterministic, offline, and built only from the facts it is given."""

    name = "demo"

    async def structured(self, system: str, user: str, schema: type[T], effort: str = "medium") -> T:
        from .schemas import Hypothesis, Rebuttal, Verdict
        kind, agent = _marker(system)
        if schema is Hypothesis:
            return self._hypothesis(agent, _facts(user))  # type: ignore[return-value]
        if schema is Rebuttal:
            return self._rebuttal(agent, user)  # type: ignore[return-value]
        if schema is Verdict:
            payload = json.loads(user.split("INPUT_JSON:", 1)[1]) if "INPUT_JSON:" in user else {}
            return self._verdict(payload)  # type: ignore[return-value]
        raise ValueError(f"DemoLLM cannot build {schema.__name__}")

    @staticmethod
    def _hypothesis(agent: str, facts):
        from .schemas import Hypothesis
        if agent == "lab":
            change = next(((i, s, ids) for i, s, ids in facts if "→" in s and "(stable)" not in s and ids), None)
            if change:
                n = len(change[2])
                return Hypothesis(claim=f"{change[1]}. This lab change is temporally associated with the symptom pattern.",
                                  leading_factor="lab_change", confidence=round(min(0.9, 0.55 + 0.1 * n), 2),
                                  evidence_ids=change[2], caveats=[f"Only {n} comparable samples"] if n <= 2 else [])
        if agent == "symptom":
            med = next(((i, s, ids) for i, s, ids in facts if " started on " in s and "→" in s), None)
            if med:
                pre, post = _ints(med[1].split("→")[0])[0], _ints(med[1].split("→")[1])[0]
                if post > pre:
                    off = next(((s, ids) for _, s, ids in facts if "outside cycle days" in s), None)
                    claim = f"{med[1]}. The rise lines up with the medication change"
                    claim += f", and {off[0][0].lower() + off[0][1:]}." if off else "."
                    ids = med[2] + (off[1] if off else [])
                    return Hypothesis(claim=claim, leading_factor="medication", evidence_ids=list(dict.fromkeys(ids)),
                                      confidence=round(0.5 + min(0.3, (post - pre) / max(post, 1) * 0.4), 2),
                                      caveats=["Other things changed in the same period"])
        if agent == "cycle":
            timing = next(((i, s, ids) for i, s, ids in facts if re.search(r"cycle days \d+–\d+", s) and " of " in s and ids), None)
            if timing:
                a, b = _ints(timing[1])[:2]
                if b and a / b >= 0.5:
                    rep = next(((s, ids) for _, s, ids in facts if s.startswith("The pattern repeats")), None)
                    claim = timing[1] + (f"; {rep[0][0].lower() + rep[0][1:]}" if rep else "") + ". This is a repeating phase pattern."
                    return Hypothesis(claim=claim, leading_factor="cycle_timing", confidence=round(0.4 + 0.3 * a / b, 2),
                                      evidence_ids=list(dict.fromkeys(timing[2] + (rep[1] if rep else []))), caveats=[])
        first = next(((i, s, ids) for i, s, ids in facts if ids), None)
        if first:
            return Hypothesis(claim=f"{first[1]}. This may be relevant, but it isn't a clear pattern yet.",
                              leading_factor="other", confidence=0.35, evidence_ids=first[2], caveats=["Weak pattern"])
        return Hypothesis(claim=f"There isn't enough {agent or 'relevant'} data in the ledger to support a hypothesis yet.",
                          leading_factor="insufficient_data", confidence=0.2, evidence_ids=[], caveats=["No supporting facts"])

    @staticmethod
    def _rebuttal(agent: str, user: str):
        from .schemas import Rebuttal
        m = re.search(r"Your hypothesis \(confidence ([0-9.]+)\)", user)
        conf = float(m.group(1)) if m else 0.5
        own = _facts(user.split("Other agents:")[0])
        if agent == "lab":
            change = next(((s, ids) for _, s, ids in own if "→" in s and "(stable)" not in s and ids), None)
            missing = next((s for _, s, _ in own if "not measured" in s), None)
            if change:
                n = len(change[1])
                text = (f"Fair challenge: {n} comparable samples can't establish a trend, so I'm lowering my confidence."
                        if n <= 2 else "The lab change holds across several samples.")
                if missing:
                    text += f" Also, {missing[0].lower() + missing[1:]}; they can't be ruled out yet."
                return Rebuttal(text=text, evidence_ids=change[1], revised_confidence=round(max(0.1, conf - 0.25) if n <= 2 else conf, 2))
        if agent == "symptom":
            off = next(((s, ids) for _, s, ids in own if "outside cycle days" in s), None)
            if off:
                return Rebuttal(text=f"Timing alone doesn't explain the increase: {off[0][0].lower() + off[0][1:]}.",
                                evidence_ids=off[1], revised_confidence=round(max(0.1, conf - 0.03), 2))
        if agent == "cycle":
            rep = next(((s, ids) for _, s, ids in own if s.startswith("The pattern repeats")), None)
            if rep:
                return Rebuttal(text=f"{rep[0]}, so timing is the most consistent signal here.",
                                evidence_ids=rep[1], revised_confidence=round(min(0.95, conf + 0.09), 2))
        ids = next((ids for _, _, ids in own if ids), [])
        return Rebuttal(text="My evidence is limited, so I'm keeping my confidence where it is.", evidence_ids=ids, revised_confidence=conf)

    @staticmethod
    def _verdict(p: dict):
        from .schemas import Adjustment, Verdict
        focus = (p.get("focus") or "symptom").lower()
        hyps = {a: h for a, h in (p.get("hypotheses") or {}).items() if h}
        rebs = p.get("rebuttals") or {}
        adj = []
        for a, h in hyps.items():
            r = rebs.get(a) or {}
            after = float(r.get("revised_confidence", h.get("confidence", 0)))
            reason = (r.get("text") or "No rebuttal round").split(". ")[0].rstrip(".")
            adj.append(Adjustment(agent=a, before=float(h.get("confidence", 0)), after=after, reason=reason))
        ranked = sorted(adj, key=lambda x: -x.after)
        factors = list(dict.fromkeys(hyps[x.agent]["leading_factor"] for x in ranked
                                     if hyps[x.agent].get("leading_factor") not in (None, "insufficient_data")))
        shared = [f.get("statement", "") for f in p.get("shared_facts") or []]
        sleep_notes = [f"Sleep: {s}" for s in shared if "sleep" in s.lower() or "night" in s.lower()]
        if not factors:
            return Verdict(single_cause_supported=False, headline=f"There isn't enough data yet to explain your {focus}.",
                           summary="None of the specialists found a supported pattern in the available records.",
                           unassigned_factors=sleep_notes, alternatives=["More records are needed"],
                           resolve_steps=["Keep logging for at least one more full cycle"],
                           clinician_questions=[f"What should I track to understand my {focus}?"], overall_confidence=0.2)
        top, rest = factors[0], factors[1:]
        verb = "follows" if top == "cycle_timing" else "is associated with"
        headline = f"Your {focus} {verb} {_PHRASE[top]}" + (f", and is also associated with {_PHRASE[rest[0]]}." if rest else ".")
        summary = (f"{len(factors)} factor{'s are' if len(factors) > 1 else ' is'} temporally associated with the {focus} pattern. "
                   f"{_PHRASE[top][0].upper() + _PHRASE[top][1:]} is the most consistent signal")
        summary += (f"; {' and '.join(_PHRASE[f] for f in rest)} {'are' if len(rest) > 1 else 'is'} also associated." if rest else ".")
        if sleep_notes:
            summary += " Sleep changed too, and no specialist owned it, so it stays an open confounder."
        claims = " ".join(h.get("claim", "") for h in hyps.values())
        texts = " ".join((r or {}).get("text", "") for r in rebs.values())
        lab_subject = re.search(r"(Day-\d+ [a-z][a-z0-9 ]*?) \d", claims)
        med_name = re.search(r"before (.+?) started on", claims)
        steps, questions = [], []
        for f in factors:
            if f == "lab_change" and lab_subject:
                steps.append(f"Repeat {lab_subject.group(1).lower()} at the same cycle day next cycle")
                questions.append(f"Should my {lab_subject.group(1).lower()} values be evaluated together with these symptoms?")
            elif f == "medication":
                steps.append("Log energy on cycle days 6–13, outside the late-luteal window")
                questions.append(f"Could {med_name.group(1) if med_name else 'the medication change'} be contributing to my {focus}?")
            elif f == "cycle_timing":
                steps.append("Keep logging through the next late-luteal window to confirm the timing")
                questions.insert(0, f"Could the timing of my {focus} relative to my cycle be relevant?")
        if re.search(r"(iron|ferritin|b12)[^.]*not measured", texts, re.I):
            steps.append("Ask your clinician whether iron/ferritin or B12 testing makes sense")
            questions.append("Would iron/ferritin or B12 testing be useful for me?")
        caveats = [c for h in hyps.values() for c in h.get("caveats") or []]
        alternatives = list(dict.fromkeys(caveats + (["Sleep disruption"] if sleep_notes else []) + ["Factors that were not logged (stress, workload)"]))
        live = [x for x in ranked if hyps[x.agent].get("leading_factor") not in (None, "insufficient_data")]
        overall = round(sum(x.after for x in live[:2]) / max(1, len(live[:2])), 2)
        return Verdict(single_cause_supported=len(factors) == 1, headline=headline, summary=summary, ranked_factors=factors,
                       adjustments=adj, unassigned_factors=sleep_notes, alternatives=alternatives,
                       resolve_steps=steps, clinician_questions=questions, overall_confidence=overall)
