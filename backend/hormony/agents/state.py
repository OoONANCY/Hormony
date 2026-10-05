from __future__ import annotations

import operator
from typing import Annotated, Dict, List, Optional, TypedDict

from .schemas import Fact, Hypothesis, Rebuttal, Verdict


class AnalysisState(TypedDict, total=False):
    patient_id: str
    question: str
    active_agents: List[str]
    facts: Dict[str, List[Fact]]
    stats: dict
    ledger_ids: List[str]
    hypotheses: Annotated[Dict[str, Optional[Hypothesis]], operator.or_]
    agent_status: Annotated[Dict[str, str], operator.or_]   # ok | paused | unavailable
    discordance: dict
    rebuttals: Annotated[Dict[str, Optional[Rebuttal]], operator.or_]
    verdict: Verdict
    report: dict
