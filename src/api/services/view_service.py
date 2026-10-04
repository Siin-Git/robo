"""View application service.

All scheduling decisions come from the existing domain function
``resolve_view_schedule``; this layer only persists rows + audit events in one
transaction (SQLite and PostgreSQL alike).
"""
from __future__ import annotations

from ...forward.views import resolve_view_schedule
from ...db.repositories.forward import ThemeRepository, ViewRepository
from ..errors import ApiError, not_found
from . import _common as C
from .participant_service import require_active


def _cfg():
    return C.load_forward_cfg()["forward_test"]


def _theme_or_404(session, theme_id: str):
    row = ThemeRepository(session).get(theme_id)
    if row is None:
        raise not_found("THEME_NOT_FOUND", f"Unknown theme {theme_id}.")
    return row


def submit(session, participant_id: str, theme_ids: list[str], reason: str,
           submitted_at=None) -> list[dict]:
    from .strategy_service import require_executable
    require_executable(theme_ids)
    ft = _cfg()
    require_active(session, participant_id)
    if len(set(theme_ids)) != len(theme_ids):
        raise ApiError("DUPLICATE_THEME", "Duplicate themes in one submission.", 400)
    if len(theme_ids) > int(ft["weekly_view"]["max_active_themes"]):
        raise ApiError("VIEW_LIMIT_EXCEEDED", "Maximum 2 active themes are allowed.", 409)
    for tid in theme_ids:
        t = _theme_or_404(session, tid)
        if not t.active or not t.ticker:
            raise ApiError("THEME_INACTIVE", f"Theme {tid} is not tradable.", 422,
                           {"inactive_reason": t.inactive_reason})
    submitted_at = submitted_at or C.now_utc()
    sched = resolve_view_schedule(submitted_at.isoformat()
                                  if hasattr(submitted_at, "isoformat") else str(submitted_at),
                                  ft["view_schedule"]["cutoff_time"])
    repo = ViewRepository(session)
    current = {v.theme_id for v in repo.active_for(participant_id)}
    if len(current | set(theme_ids)) > int(ft["weekly_view"]["max_active_themes"]):
        raise ApiError("VIEW_LIMIT_EXCEEDED",
                       "Maximum 2 active themes are allowed.", 409,
                       {"active": sorted(current)})
    out = []
    for tid in theme_ids:
        status = "hold" if tid in current else "new"
        vid = C.new_id(session, "V")
        repo.add(view_id=vid, participant_id=participant_id, theme_id=tid, status=status,
                 submitted_at=C.as_aware_utc(submitted_at),
                 effective_at=C.as_date(sched["effective_at"]),
                 end_at=None, reason=reason or "",
                 theme_universe_version=ft["theme_universe_version"],
                 cycle_week=C.as_date(sched["cycle_date"]),
                 cycle_date=C.as_date(sched["cycle_date"]))
        C.log_event(session, "VIEW_SUBMITTED", ft["benchmark_version"],
                    participant_id=participant_id,
                    payload={"view_id": vid, "theme_id": tid, "status": status,
                             "cycle_date": sched["cycle_date"], "late": sched["late"],
                             "effective_at": sched["effective_at"]})
        out.append(_out(session, vid, "PENDING"))
    session.flush()
    return out


def close(session, participant_id: str, view_id: str, closed_at=None) -> dict:
    ft = _cfg()
    repo = ViewRepository(session)
    from ...db.models.view import View as _V
    v = session.get(_V, view_id)
    if v is None or v.participant_id != participant_id:
        raise not_found("VIEW_NOT_FOUND", f"Unknown view {view_id}.")
    if not (v.status in ("new", "hold") and v.end_at is None):
        raise ApiError("VIEW_NOT_FOUND", f"View {view_id} is not active.", 404)
    closed_at = closed_at or C.now_utc()
    repo.close(view_id, C.as_aware_utc(closed_at))
    C.log_event(session, "VIEW_CLOSED", ft["benchmark_version"],
                participant_id=participant_id,
                payload={"view_id": view_id, "theme_id": v.theme_id})
    session.flush()
    return _out(session, view_id, _exec_status(session, participant_id, v.theme_id,
                                               v.effective_at))


def list_views(session, participant_id: str, status: str | None,
               limit: int, offset: int) -> tuple[list[dict], int]:
    from ...db.models.view import View as _V
    from sqlalchemy import select
    _require_participant(session, participant_id)
    q = select(_V).where(_V.participant_id == participant_id).order_by(_V.submitted_at)
    if status:
        q = q.where(_V.status == status)
    rows = list(session.scalars(q))
    total = len(rows)
    return [_out(session, r.view_id, None) for r in rows[offset:offset + limit]], total


def current(session, participant_id: str) -> list[dict]:
    _require_participant(session, participant_id)
    repo = ViewRepository(session)
    return [_out(session, v.view_id, None) for v in repo.active_for(participant_id)]


def _require_participant(session, participant_id: str):
    from ...db.models.participant import Participant as _P
    if session.get(_P, participant_id) is None:
        raise not_found("PARTICIPANT_NOT_FOUND", f"Unknown participant {participant_id}.")


def _exec_status(session, participant_id: str, theme_id: str, effective_at) -> str:
    from sqlalchemy import select
    from ...db.models.account import Account as _A
    from ...db.models.trade import Trade as _T
    from ...forward.prices import theme_asset_id
    aid = theme_asset_id(theme_id)
    accts = [a.account_id for a in session.scalars(
        select(_A).where(_A.participant_id == participant_id,
                         _A.account_type == "personal"))]
    if not accts:
        return "PENDING"
    hit = session.scalars(select(_T).where(
        _T.account_id.in_(accts), _T.asset_id == aid,
        _T.execution_at >= C.as_date(effective_at)).limit(1)).first()
    return "EXECUTED" if hit else "PENDING"


def _out(session, view_id: str, status_override: str | None) -> dict:
    from ...db.models.view import View as _V
    v = session.get(_V, view_id)
    return {"view_id": v.view_id, "participant_id": v.participant_id,
            "theme_id": v.theme_id, "status": v.status,
            "submitted_at": C.as_aware_utc(v.submitted_at),
            "cycle_date": C.as_date(v.cycle_date or v.cycle_week),
            "effective_at": C.as_date(v.effective_at),
            "execution_status": status_override or _exec_status(
                session, v.participant_id, v.theme_id, v.effective_at),
            "reason": v.reason, "theme_universe_version": v.theme_universe_version}
