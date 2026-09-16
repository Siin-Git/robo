"""Base portfolio selection service (history-preserving)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from ...db.models.base_selection import BasePortfolioSelection as _BPS
from ..errors import ApiError, not_found
from . import _common as C
from .frontier_service import FRONTIER_VERSION, find_point, get_frontier


def _now():
    return datetime.now(timezone.utc)


def get_current(session, user_id: str) -> dict | None:
    row = session.scalars(select(_BPS).where(
        _BPS.user_id == user_id, _BPS.status == "active").order_by(_BPS.selected_at.desc())).first()
    if row is None:
        return None
    return _out(row)


def list_history(session, user_id: str) -> list[dict]:
    rows = session.scalars(select(_BPS).where(_BPS.user_id == user_id).order_by(_BPS.selected_at.desc())).all()
    return [_out(r) for r in rows]


def select_base(session, user_id: str, participant_id: str, frontier_id: str) -> dict:
    point = find_point(frontier_id)
    if point is None:
        raise not_found("FRONTIER_POINT_NOT_FOUND", f"Unknown frontier_id {frontier_id}.")
    frontier = get_frontier()
    if frontier["frontier_version"] != FRONTIER_VERSION:
        raise ApiError("FRONTIER_VERSION_MISMATCH", "Frontier version mismatch.", 409)
    # Validate participant active (reuse existing check)
    from ...db.models.participant import Participant as _P
    p = session.get(_P, participant_id)
    if p is None:
        raise not_found("PARTICIPANT_NOT_FOUND", f"Unknown participant {participant_id}.")
    if p.status != "active":
        raise ApiError("PARTICIPANT_INACTIVE", "Participant is not active.", 409)
    # Supersede previous active
    prev = session.scalars(select(_BPS).where(
        _BPS.user_id == user_id, _BPS.status == "active")).all()
    for r in prev:
        r.status = "superseded"
    sel_id = C.new_id(session, "BP", 3)
    now = _now()
    weights = {w["asset_id"]: w["weight"] for w in point["weights"]}
    # Cash is not part of frontier weights; add 0 for consistency
    if "cash" not in weights:
        weights["cash"] = 0.0
    row = _BPS(selection_id=sel_id, user_id=user_id, participant_id=participant_id,
               frontier_version=FRONTIER_VERSION, frontier_id=frontier_id,
               expected_return=point["expected_return"], volatility=point["volatility"],
               sharpe=point["sharpe"], weights_json=weights,
               selected_at=now, effective_at=now, status="active")
    session.add(row)
    # Immediately materialize as a portfolio target for the personal account
    # so that dashboard / portfolio reflect the selected base without waiting
    # for the next weekly job. This is not retroactive (effective_at = now).
    from ...db.models.account import Account as _A
    from ...db.models.portfolio import PortfolioTarget as _PT
    acc = session.scalars(select(_A).where(
        _A.participant_id == participant_id, _A.account_type == "personal")).first()
    if acc is not None:
        tgt_id = C.new_id(session, "G")
        session.add(_PT(target_id=tgt_id, account_id=acc.account_id,
                        effective_date=now.date(), kind="personal",
                        weights_json=dict(weights),
                        core_version="CORE_V0.3",
                        theme_universe_version="THEME_UNIVERSE_V0.1",
                        risk_model_version="RISK_5Y_LW_FROZEN_V0",
                        created_at=now))
    # Audit event
    C.log_event(session, "BASE_PORTFOLIO_SELECTED", "CORE_V0.3", participant_id=participant_id,
                payload={"selection_id": sel_id, "frontier_id": frontier_id,
                         "frontier_version": FRONTIER_VERSION})
    session.flush()
    return _out(row)


def _out(r) -> dict:
    return {"selection_id": r.selection_id, "user_id": r.user_id,
            "participant_id": r.participant_id, "frontier_version": r.frontier_version,
            "frontier_id": r.frontier_id, "expected_return": float(r.expected_return),
            "volatility": float(r.volatility), "sharpe": float(r.sharpe) if r.sharpe is not None else None,
            "weights": [{"asset_id": k, "weight": float(v)} for k, v in dict(r.weights_json).items()],
            "selected_at": C.as_aware_utc(r.selected_at).isoformat() if r.selected_at else None,
            "effective_at": C.as_aware_utc(r.effective_at).isoformat() if r.effective_at else None,
            "status": r.status}
