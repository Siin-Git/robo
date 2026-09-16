"""Benchmark + system schemas."""
from __future__ import annotations

from pydantic import BaseModel


class SystemStatusOut(BaseModel):
    profile: str
    benchmark_version: str
    theme_universe_version: str
    benchmark_model_date: str | None = None
    benchmark_snapshot_date: str | None = None
    forward_test_inception_at: str | None = None
    first_execution_at: str | None = None
    latest_market_data_date: str | None = None
    latest_valuation_date: str | None = None
    active_participants: int = 0
    ready_to_launch: bool = False


class VersionOut(BaseModel):
    api_version: str
    benchmark_version: str
    theme_universe_version: str
