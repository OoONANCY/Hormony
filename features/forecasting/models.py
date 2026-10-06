from dataclasses import dataclass
from datetime import date
from typing import Optional, Literal


@dataclass(frozen=True)
class LedgerRow:
    """Mirror of one evidence-ledger row. Kept local so we never import main code."""
    id: str
    date: date
    kind: Literal["cycle", "lab", "symptom", "sleep", "med"]
    name: str
    value: Optional[float]
    unit: Optional[str] = None
    cycle_day: Optional[int] = None


@dataclass(frozen=True)
class CycleProjection:
    next_start: date
    expected_length_days: float
    low: date
    high: date
    confidence: float
    based_on_cycles: int


@dataclass(frozen=True)
class HormoneProjection:
    name: str
    unit: str
    points: list
    band_low: list
    band_high: list
    confidence: float
    method: str
