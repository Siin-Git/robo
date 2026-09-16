"""System routes: minimal user status, full admin status, public version."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..authz import get_current_user
from ..dependencies import get_db
from ..services import system_service as syssvc

router = APIRouter(tags=["system"])

_USER_KEYS = ("profile", "benchmark_version", "theme_universe_version",
              "benchmark_model_date", "benchmark_snapshot_date",
              "forward_test_inception_at", "first_execution_at",
              "latest_market_data_date", "latest_valuation_date",
              "active_participants", "ready_to_launch")


@router.get("/system/status", summary="System status (minimal for users)")
def system_status(db=Depends(get_db), user=Depends(get_current_user)):
    full = syssvc.status(db)
    return {k: full.get(k) for k in _USER_KEYS}


@router.get("/version", summary="API + model versions")
def version():
    return syssvc.version()
