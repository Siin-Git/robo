"""Participant schemas."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class ParticipantCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=128)


class ParticipantOut(BaseModel):
    participant_id: str
    display_name: str
    status: str
    join_date: date
    leave_date: date | None = None
    created_at: datetime
    updated_at: datetime
