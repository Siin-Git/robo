"""Benchmark schemas."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class BenchmarkInfo(BaseModel):
    benchmark_version: str
    display_name: str


class BenchmarkNavPoint(BaseModel):
    date: date
    nav: float


class BenchmarkPerformanceOut(BaseModel):
    items: list[BenchmarkNavPoint]
