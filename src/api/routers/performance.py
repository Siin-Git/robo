"""Performance routes (owner-scoped; rankings visible to any login)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..authz import enforce_owner, get_current_user
from ..dependencies import get_db
from ..errors import ApiError
from ..services import performance_service as svc

router = APIRouter(tags=["performance"])


@router.get("/participants/{participant_id}/performance", summary="Performance summary")
def get_performance(participant_id: str, start: str | None = Query(default=None),
                    end: str | None = Query(default=None), db=Depends(get_db),
                    user=Depends(get_current_user)):
    enforce_owner(user, participant_id)
    return svc.summary(db, participant_id, start, end)


@router.get("/participants/{participant_id}/performance/nav", summary="NAV history")
def get_nav_history(participant_id: str, db=Depends(get_db),
                    user=Depends(get_current_user)):
    enforce_owner(user, participant_id)
    return svc.nav_history(db, participant_id)


@router.get("/participants/{participant_id}/performance/active", summary="Active returns")
def get_active(participant_id: str, db=Depends(get_db),
               user=Depends(get_current_user)):
    enforce_owner(user, participant_id)
    return svc.active_returns(db, participant_id)


@router.get("/participants/{participant_id}/performance/attribution",
            summary="Return attribution")
def get_attribution(participant_id: str, start: str | None = Query(default=None),
                    end: str | None = Query(default=None), db=Depends(get_db),
                    user=Depends(get_current_user)):
    enforce_owner(user, participant_id)
    return svc.attribution(db, participant_id, start, end)


@router.get("/rankings", summary="Participant rankings")
def get_rankings(period: str = Query(default="weekly"),
                 basis: str = Query(default="active_return"),
                 comparison: str = Query(default="common_period"),
                 db=Depends(get_db), user=Depends(get_current_user)):
    if period != "weekly":
        raise ApiError("INVALID_PERIOD", "Only period=weekly is supported in V0.", 400)
    if comparison not in ("common_period", "since_inception"):
        raise ApiError("INVALID_COMPARISON",
                       "comparison must be common_period or since_inception.", 400)
    full = svc.rankings(db, period, basis, comparison)
    # Public ranking surface: display names + performance only, never emails.
    return {"items": [{"rank": i["rank"], "participant_id": i["participant_id"],
                       "display_name": i["display_name"],
                       "current_themes": i.get("current_themes", []),
                       "active_return": i["active_return"],
                       "cumulative": i.get("cumulative"), "mdd": i.get("mdd"),
                       "te": i.get("te")} for i in full["items"]],
            "period": full["period"], "basis": full["basis"],
            "comparison": full["comparison"]}
