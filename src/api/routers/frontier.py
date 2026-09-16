"""Frontier + base portfolio routes (user-scoped, no frontend math)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..authz import get_current_user, require_csrf
from ..dependencies import get_db
from ..services import base_portfolio_service as base_svc
from ..services import frontier_service as frontier_svc
from pydantic import BaseModel

router = APIRouter(tags=["frontier"])


class SelectBody(BaseModel):
    frontier_id: str


@router.get("/portfolio/frontier", summary="Efficient Frontier (CORE_FRONTIER_V0.3)")
def get_frontier(db=Depends(get_db), user=Depends(get_current_user)):
    return frontier_svc.get_frontier()


@router.get("/me/frontier", summary="Efficient Frontier (user view)")
def get_my_frontier(db=Depends(get_db), user=Depends(get_current_user)):
    return frontier_svc.get_frontier()


@router.get("/me/base-portfolio", summary="Current base portfolio selection")
def get_base(db=Depends(get_db), user=Depends(get_current_user)):
    cur = base_svc.get_current(db, user.user_id)
    if cur is None:
        return {"status": "not_selected", "message": "No base portfolio selected yet."}
    return {"status": "selected", **cur, "portfolio_mode": "user_selected"}


@router.post("/me/base-portfolio", summary="Select base portfolio from frontier")
def select_base(body: SelectBody, db=Depends(get_db), user=Depends(require_csrf)):
    if not user.participant_id:
        from ..errors import ApiError
        raise ApiError("NO_PARTICIPANT", "User has no linked participant.", 409)
    return base_svc.select_base(db, user.user_id, user.participant_id, body.frontier_id)


@router.get("/me/base-portfolio/history", summary="Base portfolio selection history")
def history(db=Depends(get_db), user=Depends(get_current_user)):
    return {"items": base_svc.list_history(db, user.user_id)}
