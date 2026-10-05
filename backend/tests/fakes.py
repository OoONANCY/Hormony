from __future__ import annotations
from typing import Dict
from pydantic import BaseModel


class FakeLLM:
    """Keyed by marker in system, e.g. '[agent:lab]'. Records calls."""

    name = "fake"

    def __init__(self, responses: Dict[str, BaseModel]):
        self.responses = responses
        self.calls: list[dict] = []

    async def structured(self, system: str, user: str, schema, effort: str = "medium"):
        self.calls.append({"system": system, "user": user, "schema": getattr(schema, "__name__", str(schema)), "effort": effort})
        for marker, resp in self.responses.items():
            if marker in system:
                if isinstance(resp, schema):
                    return resp
                # allow dicts
                if isinstance(resp, dict):
                    return schema(**resp)
                return resp
        # fallback: build empty schema if possible
        raise AssertionError(f"FakeLLM: no response for system={system[:80]!r}")
