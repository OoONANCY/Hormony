from __future__ import annotations
from datetime import date as Date, datetime as DateTime
from typing import Optional
from sqlalchemy import String, Float, Integer, Date, DateTime, JSON, PrimaryKeyConstraint, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (PrimaryKeyConstraint("patient_id", "id"),)  # record ids are unique per person, not globally
    id: Mapped[str] = mapped_column(String(40))
    patient_id: Mapped[str] = mapped_column(String(40), index=True)
    date: Mapped[Date] = mapped_column(Date, index=True)
    type: Mapped[str] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(String(80))
    code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, default=None)
    value: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)
    unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, default=None)
    severity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=None)
    note: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(80), default="")
    source_ref: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, default=None)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())


class Profile(Base):
    __tablename__ = "profiles"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    kind: Mapped[str] = mapped_column(String(10), default="personal")   # demo | personal
    cycle_length: Mapped[int] = mapped_column(Integer, default=28)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())


class ReportFile(Base):
    __tablename__ = "report_files"
    __table_args__ = (PrimaryKeyConstraint("patient_id", "id"),)  # the same file can belong to more than one person
    id: Mapped[str] = mapped_column(String(64))                          # sha256 of the file
    patient_id: Mapped[str] = mapped_column(String(40), index=True)
    filename: Mapped[str] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(String(80))
    path: Mapped[str] = mapped_column(String(300))
    pages: Mapped[int] = mapped_column(Integer, default=1)
    method: Mapped[str] = mapped_column(String(10), default="")          # text | vision | rules
    extraction: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=None)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    patient_id: Mapped[str] = mapped_column(String(40))
    question: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="running")
    result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=None)
    event_log: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=None)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
