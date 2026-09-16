"""System application service (status + version)."""
from __future__ import annotations

import os

from sqlalchemy import select

from ...db.models.nav import NavDaily as _N
from ...db.models.operational import ForwardState
from ...db.models.participant import Participant as _P
from ...db.models.price import PriceDaily as _Px
from ...db.models.theme import Theme as _T
from . import _common as C


def _lifecycle(session, key: str):
    try:
        row = session.get(ForwardState, key)
        return row.value if row else None
    except Exception:
        return None


def status(session) -> dict:
    from ...db.config import get_backend
    cfg = C.load_forward_cfg()["forward_test"]
    backend = get_backend()
    try:
        frozen_w, meta = C.frozen_bundle()
        benchmark_ok = True
    except Exception:
        frozen_w, meta, benchmark_ok = {}, {}, False
    active_p = session.scalars(select(_P).where(_P.status == "active")).all()
    themes = session.scalars(select(_T).where(_T.active.is_(True))).all()
    lastpx = session.scalars(select(_Px.date).order_by(_Px.date.desc())).first()
    lastnav = session.scalars(select(_N.date).order_by(_N.date.desc())).first()
    inception = _lifecycle(session, "forward_test_inception_at")
    first_exec = _lifecycle(session, "first_execution_at")
    ready = bool(benchmark_ok and themes)
    return {"profile": _profile(), "backend": backend,
            "benchmark_version": cfg["benchmark_version"],
            "theme_universe_version": cfg["theme_universe_version"],
            "benchmark_model_date": (meta.get("run_timestamp", "") or "")[:10] or None,
            "benchmark_snapshot_date": meta.get("data_end"),
            "forward_test_inception_at": inception,
            "first_execution_at": first_exec,
            "latest_market_data_date": C.as_date(lastpx),
            "latest_valuation_date": C.as_date(lastnav),
            "active_participants": len(active_p),
            "ready_to_launch": ready and inception is None,
            "database": _safe_db_url()}


def version() -> dict:
    cfg = C.load_forward_cfg()["forward_test"]
    return {"api_version": "0.1.0", "benchmark_version": cfg["benchmark_version"],
            "theme_universe_version": cfg["theme_universe_version"]}


def _profile() -> str:
    return os.environ.get("APP_PROFILE", "live").strip().lower()


def _safe_db_url() -> str:
    try:
        from ...db.config import get_database_url
        from sqlalchemy.engine import make_url
        u = make_url(get_database_url())
        return str(u.set(password="***")) if u.password else str(u)
    except Exception as e:
        return f"unavailable ({e})"
