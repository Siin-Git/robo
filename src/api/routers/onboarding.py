"""Onboarding draft + preview + complete routes (3-step)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..authz import get_current_user
from ..design_workspace import get_design_db, require_design_csrf
from ..services import onboarding_service as svc
from ..errors import ApiError

router = APIRouter(prefix="/me/onboarding", tags=["onboarding"])

class DraftBody(BaseModel):
    frontier_id: str | None = None
    theme_ids: list[str] | None = None
    reason: str | None = None
    current_step: str = "risk"

class PreviewBody(BaseModel):
    frontier_id: str
    theme_ids: list[str] = []

class CompleteBody(BaseModel):
    frontier_id: str
    theme_ids: list[str] = []
    reason: str | None = None

def _pid(user):
    if not user.participant_id:
        raise ApiError("NO_PARTICIPANT", "User has no linked participant.", 409)
    return user.participant_id

@router.get("/draft", summary="Get onboarding draft")
def get_draft(db=Depends(get_design_db), user=Depends(get_current_user)):
    d = svc.get_draft(db, user.user_id)
    if d is None:
        return {"status": "not_started"}
    return {"status": "draft", **d}

@router.put("/draft", summary="Upsert onboarding draft")
def put_draft(body: DraftBody, db=Depends(get_design_db), user=Depends(require_design_csrf)):
    d = svc.upsert_draft(db, user.user_id, _pid(user), body.frontier_id, body.theme_ids, body.reason, body.current_step)
    return d

@router.post("/draft", summary="Upsert onboarding draft (POST alias)")
def post_draft(body: DraftBody, db=Depends(get_design_db), user=Depends(require_design_csrf)):
    d = svc.upsert_draft(db, user.user_id, _pid(user), body.frontier_id, body.theme_ids, body.reason, body.current_step)
    return d

@router.post("/preview", summary="Preview personalized portfolio for onboarding")
def preview(body: PreviewBody, db=Depends(get_design_db), user=Depends(get_current_user)):
    return svc.preview(db, user.user_id, _pid(user), body.frontier_id, body.theme_ids)

@router.post("/complete", summary="Complete onboarding (creates base + themes + target)")
def complete(body: CompleteBody, db=Depends(get_design_db), user=Depends(require_design_csrf)):
    return svc.complete(db, user.user_id, _pid(user), body.frontier_id, body.theme_ids, body.reason)
