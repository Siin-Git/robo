"""Performance schemas."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class PerformanceOut(BaseModel):
    status: str
    metrics: dict


class NavPoint(BaseModel):
    date: date
    personalized_nav: float | None = None
    core_nav: float | None = None


class NavHistoryOut(BaseModel):
    items: list[NavPoint]


class ActiveReturnOut(BaseModel):
    daily: list[dict] = []
    weekly: float | None = None
    cumulative: float | None = None


class ThemeContribution(BaseModel):
    theme_id: str
    contribution: float


class AttributionOut(BaseModel):
    core_return: float | None = None
    active_return: float | None = None
    transaction_cost: float | None = None
    theme_contributions: list[ThemeContribution] = []


class RankingItem(BaseModel):
    rank: int
    participant_id: str
    display_name: str
    active_return: float | None = None


class RankingOut(BaseModel):
    items: list[RankingItem]
    period: str
    basis: str
    comparison: str
