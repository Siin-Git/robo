"""Benchmark routes (thin wrappers; logic lives in benchmark_service)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..authz import get_current_user
from ..dependencies import get_db
from ..services import benchmark_service as svc

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])


@router.get("/definitions", summary="Benchmark candidates and explicitly approved definitions")
def benchmark_definitions(user=Depends(get_current_user)):
    from ..services.benchmark_definition_service import definitions
    return definitions()


@router.get("", summary="Available benchmarks")
def list_benchmarks(user=Depends(get_current_user)):
    return {"items": svc.list_benchmarks()}


@router.get("/performance", summary="Shadow NAV history")
def benchmark_performance(
        benchmark_version: str = Query(default="CORE_V0.3"),
        db=Depends(get_db), user=Depends(get_current_user)):
    return svc.shadow_performance(db, benchmark_version)
