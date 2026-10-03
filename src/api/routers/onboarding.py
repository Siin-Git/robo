"""Onboarding draft + preview + complete routes (3-step)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..authz import get_current_user, require_authenticated_csrf
from ..design_workspace import get_design_db
from ..services import onboarding_service as svc, enrollment_service, market_comparison
from ..errors import ApiError
from ..dependencies import get_db

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
    adjustment_choice_id: str | None = None
    expected_decision_id: str | None = None
    frontier_id: str
    theme_ids: list[str] = []
    reason: str | None = None

def _pid(user):
    if not user.participant_id:
        raise ApiError("NO_PARTICIPANT", "User has no linked participant.", 409)
    return user.participant_id

@router.get("/draft", summary="Get onboarding draft")
def get_draft(db=Depends(get_design_db), user=Depends(get_current_user), auth_db=Depends(get_db)):
    from ..services.enrollment_service import own
    slot = own(auth_db, user)
    if slot and not slot.confirmed_at:
        if market_comparison.enabled():
            d = slot.draft_json or {}
            return {"status": "draft" if d.get("frontier_id") else "not_started",
                "frontier_id": d.get("frontier_id"), "theme_ids": d.get("theme_ids", []),
                "reason": d.get("reason", ""), "current_step": d.get("current_step", "risk")}
        return {"status": "not_started"}
    d = svc.get_draft(db, user.user_id)
    if d is None:
        if market_comparison.enabled():
            cfg = market_comparison.configuration(auth_db, user, enrollment_service.own(auth_db, user))
            return {"status": "saved", "frontier_id": cfg["frontier_id"],
                "theme_ids": [a[6:] for a in cfg["weights"] if a.startswith("theme:") and cfg["weights"][a] > 0],
                "reason": cfg["reason"], "current_step": "risk"}
        return {"status": "not_started"}
    return {"status": "draft", **d}

@router.put("/draft", summary="Upsert onboarding draft")
def put_draft(body: DraftBody, db=Depends(get_design_db), user=Depends(require_authenticated_csrf), auth_db=Depends(get_db)):
    slot = enrollment_service.own(auth_db, user)
    if slot and not slot.confirmed_at:
        if not market_comparison.enabled():
            raise ApiError("SETUP_REQUIRED", "먼저 첫 설정을 완료해 주세요.", 409)
        data = {**(slot.draft_json or {}), **body.model_dump(exclude_none=True), "core_id": "CORE_V0.3"}
        return enrollment_service.save_draft(auth_db, user, data)["draft"]
    d = svc.upsert_draft(db, user.user_id, _pid(user), body.frontier_id, body.theme_ids, body.reason, body.current_step)
    return d

@router.post("/draft", summary="Upsert onboarding draft (POST alias)")
def post_draft(body: DraftBody, db=Depends(get_design_db), user=Depends(require_authenticated_csrf), auth_db=Depends(get_db)):
    return put_draft(body, db, user, auth_db)

@router.post("/preview", summary="Preview personalized portfolio for onboarding")
def preview(body: PreviewBody, db=Depends(get_design_db), user=Depends(get_current_user)):
    return svc.preview(db, user.user_id, _pid(user), body.frontier_id, body.theme_ids)

@router.post("/complete", summary="Complete onboarding (creates base + themes + target)")
def complete(body: CompleteBody, db=Depends(get_design_db), user=Depends(require_authenticated_csrf), auth_db=Depends(get_db)):
    slot = enrollment_service.own(auth_db, user)
    if slot and not slot.confirmed_at:
        if not market_comparison.enabled():
            raise ApiError("SETUP_REQUIRED", "먼저 첫 설정을 완료해 주세요.", 409)
        result = enrollment_service.complete(auth_db, user, {**body.model_dump(), "reason": body.reason or "", "core_id": "CORE_V0.3"})
        result.update(svc.complete(db, user.user_id, _pid(user), body.frontier_id, body.theme_ids, body.reason, body.adjustment_choice_id, expected_decision_id=body.expected_decision_id))
        return result
    return svc.complete(db, user.user_id, _pid(user), body.frontier_id, body.theme_ids, body.reason, body.adjustment_choice_id, expected_decision_id=body.expected_decision_id)
