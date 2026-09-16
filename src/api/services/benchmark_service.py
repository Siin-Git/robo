"""Benchmark application service (frozen weights + shadow NAVs)."""
from __future__ import annotations

from sqlalchemy import select

from ...db.models.account import Account as _A
from ...db.models.nav import NavDaily as _N
from ..errors import ApiError
from . import _common as C

SHADOWS = (("CORE_V0.3", "CORE_V0.3", "core_v03"),
           ("neutral_60_40", "Neutral 60/40", "neutral_60_40"),
           ("equal_weight", "Equal Weight", "equal_weight"))
_BENCH_TO_SHADOW = {b: s for b, _, s in SHADOWS}


def list_benchmarks() -> list[dict]:
    return [{"benchmark_version": b, "display_name": n} for b, n, _ in SHADOWS]


def shadow_performance(session, benchmark_version: str) -> dict:
    shadow = _BENCH_TO_SHADOW.get(benchmark_version)
    if shadow is None:
        raise ApiError("BENCHMARK_NOT_FOUND", f"Unknown benchmark {benchmark_version}.", 404)
    acc = session.scalars(select(_A).where(
        _A.account_type == "shadow", _A.shadow_name == shadow)).first()
    if acc is None:
        # Pre-launch: shadow account not created yet -> empty history, not an error.
        return {"items": []}
    rows = list(session.scalars(select(_N).where(_N.account_id == acc.account_id)
                                .order_by(_N.date)))
    base = float(rows[0].nav) if rows else 1.0
    return {"items": [{"date": C.as_date(r.date),
                       "nav": float(r.nav) / base * 100.0} for r in rows]}
