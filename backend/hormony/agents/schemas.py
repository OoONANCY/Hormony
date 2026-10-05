from __future__ import annotations
from typing import Literal, Optional, List
from pydantic import BaseModel, Field

AgentName = Literal["lab", "symptom", "cycle"]
LeadingFactor = Literal["cycle_timing", "medication", "lab_change", "sleep", "other", "insufficient_data"]


class Fact(BaseModel):
    id: str
    statement: str
    evidence_ids: List[str] = Field(default_factory=list)


class Hypothesis(BaseModel):
    claim: str = Field(description="One or two sentences. Associations only, never causation.")
    leading_factor: LeadingFactor
    confidence: float = Field(ge=0, le=1)
    evidence_ids: List[str] = Field(description="Ledger IDs copied from the facts you used")
    caveats: List[str] = Field(default_factory=list)


class Rebuttal(BaseModel):
    text: str
    evidence_ids: List[str] = Field(default_factory=list)
    revised_confidence: float = Field(ge=0, le=1)


class Adjustment(BaseModel):
    agent: AgentName
    before: float
    after: float
    reason: str


class Verdict(BaseModel):
    single_cause_supported: bool
    headline: str
    summary: str
    ranked_factors: List[str] = Field(default_factory=list)
    adjustments: List[Adjustment] = Field(default_factory=list)
    unassigned_factors: List[str] = Field(default_factory=list)
    alternatives: List[str] = Field(default_factory=list)
    resolve_steps: List[str] = Field(default_factory=list)
    clinician_questions: List[str] = Field(
        default_factory=list,
        description="Questions in the first person that the person can ask their clinician, e.g. "
                    "'Could my fatigue be related to the medication change?'. Never questions addressed to the person.")
    overall_confidence: float = Field(ge=0, le=1)
