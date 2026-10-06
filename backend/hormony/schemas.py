from __future__ import annotations

from datetime import date as Date
from typing import Optional

from pydantic import BaseModel, Field


class EventOut(BaseModel):
    id: str
    date: Date
    type: str
    name: str
    code: Optional[str] = None
    value: Optional[float] = None
    unit: Optional[str] = None
    severity: Optional[int] = None
    note: str = ""
    source: str = ""
    source_ref: Optional[str] = None
    cycle_day: Optional[int] = None
    phase: Optional[str] = None


class EventIn(BaseModel):
    # lengths mirror the database columns so bad input is a 422, never a database error
    date: Optional[Date] = None
    type: str = Field(max_length=10)
    name: Optional[str] = Field(None, max_length=80)
    code: Optional[str] = Field(None, max_length=10)
    value: Optional[float] = None
    unit: Optional[str] = Field(None, max_length=20)
    severity: Optional[int] = None
    note: str = Field("", max_length=2000)
    source: Optional[str] = Field(None, max_length=80)
    source_ref: Optional[str] = Field(None, max_length=200)


class TimelineOut(BaseModel):
    events: list[EventOut]
    cycle_starts: list[Date]
    today: Date


class SummaryOut(BaseModel):
    counts: dict[str, int]
    days_tracked: int


class WearableIn(BaseModel):
    date: Optional[Date] = None

    sleep_hours: Optional[float] = Field(
        None,
        ge=0,
        le=24
    )

    resting_heart_rate: Optional[float] = Field(
        None,
        ge=20,
        le=250
    )

    hrv: Optional[float] = Field(
        None,
        ge=0,
        le=500
    )

    steps: Optional[int] = Field(
        None,
        ge=0,
        le=200000
    )

    body_temperature: Optional[float] = Field(
        None,
        ge=25,
        le=45
    )

    source: str = Field(
        "wearable",
        max_length=80
    )

    source_ref: Optional[str] = Field(
        None,
        max_length=200
    )


class WearableOut(BaseModel):
    date: Date
    sleep_hours: Optional[float] = None
    resting_heart_rate: Optional[float] = None
    hrv: Optional[float] = None
    steps: Optional[int] = None
    body_temperature: Optional[float] = None
    source: str
