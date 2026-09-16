"""Portfolio schemas."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class WeightLeg(BaseModel):
    asset_id: str
    weight: float
    asset_type: str = "core"
    ticker: str | None = None


class PortfolioOut(BaseModel):
    participant_id: str | None = None
    as_of: date | None = None
    benchmark_version: str
    expected_volatility: float | None = None
    tracking_error: float | None = None
    weights: list[WeightLeg]


class CorePortfolioOut(BaseModel):
    benchmark_version: str
    model_date: str | None = None
    snapshot_date: str | None = None
    weights: list[WeightLeg]


class ComparisonOut(BaseModel):
    core: list[WeightLeg]
    personalized: list[WeightLeg]
    active: list[WeightLeg]
