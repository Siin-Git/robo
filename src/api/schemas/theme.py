"""Theme schemas."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class ThemeOut(BaseModel):
    theme_id: str
    display_name: str
    theme_type: str
    ticker: str | None = None
    market: str | None = None
    currency: str | None = None
    active: bool
    universe_version: str
    valid_from: date | None = None
    valid_to: date | None = None
    inactive_reason: str | None = None
