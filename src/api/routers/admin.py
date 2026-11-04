"""Admin routes (development only — no auth in Phase 3B, require_admin in 3C).

All routes here require the admin role.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from typing import Literal
from pydantic import BaseModel, Field

from ..authz import require_admin, require_authenticated_csrf
from ..design_workspace import get_admin_design_db
from ..dependencies import get_db
from ..services import auth_service as auth
from ..services import system_service as syssvc

router = APIRouter(prefix="/admin", tags=["admin"])


class InternalReviewBody(BaseModel):
    asset_id: str = Field(min_length=1, max_length=64)
    action: Literal["KEEP_OBSERVING", "REVISION_REVIEW"]
    reason: str = Field(min_length=1, max_length=1024)
    request_key: str = Field(min_length=8, max_length=64)


@router.get("/tracking", summary="Internal decision diagnostics (admin)")
def internal_decisions(limit: int = Query(default=50, ge=1, le=200),
                       offset: int = Query(default=0, ge=0),
                       db=Depends(get_admin_design_db), admin=Depends(require_admin)):
    from ..services import internal_tracking_service as tracking
    return tracking.list_decisions(db, limit, offset)


@router.get("/tracking/{decision_id}", summary="Per-asset internal tracking (admin)")
def internal_report(decision_id: str, db=Depends(get_admin_design_db), admin=Depends(require_admin)):
    from ..services import internal_tracking_service as tracking
    return tracking.report(db, decision_id)


@router.post("/tracking/{decision_id}/reviews", dependencies=[Depends(require_authenticated_csrf)],
             summary="Append internal revision review; does not change trading (admin)")
def internal_review(decision_id: str, body: InternalReviewBody,
                    db=Depends(get_admin_design_db), admin=Depends(require_admin)):
    from ..services import internal_tracking_service as tracking
    return tracking.record_review(db, admin.user_id, decision_id, **body.model_dump())


@router.get("/users", summary="List users (admin)")
def list_users(limit: int = Query(default=50, ge=1, le=200),
               offset: int = Query(default=0, ge=0),
               db=Depends(get_db), admin=Depends(require_admin)):
    from ...db.repositories.forward import UserRepository
    rows, total = UserRepository(db).list(limit, offset)
    return {"items": [{"user_id": u.user_id, "email": u.email, "role": u.role,
                       "status": u.status, "participant_id": u.participant_id}
                      for u in rows],
            "total": total, "limit": limit, "offset": offset}


@router.get("/users/{user_id}", summary="User detail (admin)")
def get_user(user_id: str, db=Depends(get_db), admin=Depends(require_admin)):
    from ...db.models.user import User as _U
    u = db.get(_U, user_id)
    if u is None:
        from ..errors import ApiError
        raise ApiError("USER_NOT_FOUND", f"Unknown user {user_id}.", 404)
    return {"user_id": u.user_id, "email": u.email, "role": u.role,
            "status": u.status, "participant_id": u.participant_id}


@router.post("/users/{user_id}/disable", summary="Disable user (admin)")
def disable_user(user_id: str, db=Depends(get_db), admin=Depends(require_admin)):
    return auth.disable_user(db, user_id)


@router.post("/users/{user_id}/enable", summary="Enable user (admin)")
def enable_user(user_id: str, db=Depends(get_db), admin=Depends(require_admin)):
    return auth.enable_user(db, user_id)


@router.get("/orders/pending", summary="Pending orders (admin)")
def pending_orders(db=Depends(get_db), admin=Depends(require_admin)):
    from ...db.repositories.forward import OrderRepository
    rows = OrderRepository(db).pending()
    return {"items": [{"order_id": o.order_id, "account_id": o.account_id,
                       "asset_id": o.asset_id, "side": o.side,
                       "target_weight": float(o.target_weight),
                       "submitted_at": o.submitted_at.isoformat()
                       if hasattr(o.submitted_at, "isoformat") else str(o.submitted_at),
                       "effective_at": str(o.effective_at), "status": o.status}
                      for o in rows]}


@router.get("/trades", summary="Recent trades (admin)")
def recent_trades(participant_id: str | None = Query(default=None),
                  account_id: str | None = Query(default=None),
                  start: str | None = Query(default=None),
                  end: str | None = Query(default=None),
                  limit: int = Query(default=50, ge=1, le=200),
                  offset: int = Query(default=0, ge=0),
                  db=Depends(get_db), admin=Depends(require_admin)):
    from sqlalchemy import select
    from ...db.models.trade import Trade as _T
    q = select(_T).order_by(_T.execution_at.desc())
    if account_id:
        q = q.where(_T.account_id == account_id)
    if start:
        q = q.where(_T.execution_at >= start)
    if end:
        q = q.where(_T.execution_at <= end)
    rows = list(db.scalars(q))
    if participant_id:
        from ...db.models.account import Account as _A
        mine = {a.account_id for a in db.scalars(
            select(_A).where(_A.participant_id == participant_id))}
        rows = [r for r in rows if r.account_id in mine]
    total = len(rows)
    page = rows[offset:offset + limit]
    return {"items": [{"trade_id": r.trade_id, "order_id": r.order_id,
                       "account_id": r.account_id, "asset_id": r.asset_id,
                       "execution_at": str(r.execution_at),
                       "execution_price": float(r.execution_price),
                       "quantity": float(r.quantity),
                       "gross_value": float(r.gross_value),
                       "transaction_cost": float(r.transaction_cost),
                       "net_value": float(r.net_value)} for r in page],
            "total": total, "limit": limit, "offset": offset}


@router.get("/system/status", summary="Operational status (admin)")
def admin_system_status(db=Depends(get_db), admin=Depends(require_admin)):
    return syssvc.status(db)


@router.get("/jobs", summary="Scheduled job runs (admin)")
def job_runs(limit: int = Query(default=20, ge=1, le=200),
             db=Depends(get_db), admin=Depends(require_admin)):
    from ...forward import jobs as _jobs
    try:
        url = str(db.get_bind().url)
        if url.startswith("sqlite"):
            import pathlib
            rows = _jobs.recent_jobs(None, limit, sqlite_path=pathlib.Path(
                db.get_bind().url.database))
        else:
            rows = _jobs.recent_jobs(url, limit)
    except Exception as e:
        rows = []
        return {"items": [], "note": f"job registry unavailable: {e}"}
    return {"items": [{k: (str(v) if v is not None else None) for k, v in r.items()}
                      for r in rows]}
