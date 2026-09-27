"""Self-service routes: the primary frontend contract (no participant_id needed)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..authz import get_current_user
from ..dependencies import get_db
from ..design_workspace import get_design_db, require_design_csrf
from ..errors import ApiError
from ..schemas.view import ViewSubmit
from ..services import performance_service as perf
from ..services import performance_report_service as reports
from ..services import ledger_read_service as ledger_reads
from ..services import portfolio_service as pf
from ..services import view_service as views

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/comparison", summary="Own demo comparison snapshot")
def me_comparison_snapshot(db=Depends(get_db), user=Depends(get_current_user)):
    from ..services.comparison_service import detail
    return detail(db, _pid(user))


def _pid(user) -> str:
    if not user.participant_id:
        raise ApiError("NO_PARTICIPANT", "User has no linked participant.", 409)
    return user.participant_id


@router.get("", summary="Current user profile")
def me_profile(user=Depends(get_current_user)):
    return {"user_id": user.user_id, "email": user.email, "role": user.role,
            "status": user.status, "participant_id": user.participant_id}


@router.get("/portfolio", summary="Own personalized portfolio")
def me_portfolio(db=Depends(get_design_db), user=Depends(get_current_user)):
    return pf.personalized(db, _pid(user), user.user_id)


@router.get("/portfolio/summary", summary="Own portfolio summary (base + personalized)")
def me_summary(db=Depends(get_design_db), user=Depends(get_current_user)):
    return pf.summary(db, _pid(user), user.user_id)


@router.get("/portfolio/comparison", summary="Own core vs personalized")
def me_comparison(db=Depends(get_design_db), user=Depends(get_current_user)):
    return pf.comparison(db, _pid(user))


@router.get("/views", summary="Own view history")
def me_views(status: str | None = Query(default=None),
             limit: int = Query(default=50, ge=1, le=200),
             offset: int = Query(default=0, ge=0),
             db=Depends(get_design_db), user=Depends(get_current_user)):
    items, total = views.list_views(db, _pid(user), status, limit, offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/views/current", summary="Own active views")
def me_views_current(db=Depends(get_design_db), user=Depends(get_current_user)):
    items = views.current(db, _pid(user))
    return {"items": items, "total": len(items)}


@router.post("/views", status_code=201, summary="Submit own views")
def me_views_submit(body: ViewSubmit, db=Depends(get_design_db), user=Depends(require_design_csrf)):
    return {"views": views.submit(db, _pid(user), body.theme_ids, body.reason)}


@router.get("/performance", summary="Own performance")
def me_performance(start: str | None = Query(default=None),
                   end: str | None = Query(default=None),
                   db=Depends(get_design_db), user=Depends(get_current_user)):
    return perf.summary(db, _pid(user), start, end)


@router.get("/performance/nav", summary="Own NAV history")
def me_nav(db=Depends(get_design_db), user=Depends(get_current_user)):
    return perf.nav_history(db, _pid(user))


@router.get("/performance/dashboard", summary="Period-aligned performance and asset contribution")
def me_performance_dashboard(period: str = Query(default="ALL"),
                             db=Depends(get_design_db), user=Depends(get_current_user)):
    return reports.dashboard(db, _pid(user), period)


@router.get("/performance/contributions", summary="Own cumulative asset return contributions")
def me_performance_contributions(period: str = Query(default="ALL"),
                                 db=Depends(get_db), user=Depends(get_current_user)):
    return reports.cumulative_contributions(db, _pid(user), period)


@router.get("/performance/ledger", summary="Own persisted ledger for performance calculations")
def me_performance_ledger(start: str | None = Query(default=None),
                          end: str | None = Query(default=None),
                          db=Depends(get_db), user=Depends(get_current_user)):
    return ledger_reads.ledger(db, _pid(user), start, end)


@router.get("/performance/active", summary="Own active returns")
def me_active(db=Depends(get_design_db), user=Depends(get_current_user)):
    return perf.active_returns(db, _pid(user))


@router.get("/performance/attribution", summary="Own attribution")
def me_attribution(db=Depends(get_design_db), user=Depends(get_current_user)):
    return perf.attribution(db, _pid(user))
