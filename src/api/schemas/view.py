"""View schemas."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class ViewSubmit(BaseModel):
    theme_ids: list[str] = Field(min_length=1, max_length=2)
    reason: str = Field(default="", max_length=1024)


class ViewOut(BaseModel):
    view_id: str
    participant_id: str
    theme_id: str
    status: str
    submitted_at: datetime
    cycle_date: date
    effective_at: date
    execution_status: str = "PENDING"
    reason: str | None = None
    theme_universe_version: str
