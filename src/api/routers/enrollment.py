"""Narrow demo write exception: reserved users' initial experiment setup only."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Literal
from ..authz import get_current_user, require_authenticated_csrf
from ..dependencies import get_db
from ..design_workspace import get_design_db, enabled as design_enabled
from ..services import enrollment_service as svc

router = APIRouter(prefix="/me/experiment", tags=["onboarding"])

class Configuration(BaseModel):
    core_id: str
    frontier_id: str | None = None
    theme_ids: list[str] = Field(default_factory=list, max_length=2)
    reason: str = Field(default="", max_length=1024)
    current_step: str = Field(default="risk", pattern="^(risk|themes|review)$")

class ResetBody(BaseModel):
    confirm: Literal[True]
    model_config = {"extra": "forbid"}

@router.post("/reset")
def reset(body: ResetBody, db=Depends(get_db), user=Depends(require_authenticated_csrf)):
    return svc.reset_portfolio(db, user)

@router.get("")
def status(db=Depends(get_db), user=Depends(get_current_user)):
    return svc.status(db, user)

@router.get("/conditions")
def conditions(db=Depends(get_db), user=Depends(get_current_user)):
    svc.require_slot(db, user)
    return svc.conditions(db)

@router.put("/draft")
def draft(body: Configuration, db=Depends(get_db), user=Depends(require_authenticated_csrf)):
    return svc.save_draft(db, user, body.model_dump())

@router.post("/preview")
def preview(body: Configuration, db=Depends(get_db), user=Depends(get_current_user)):
    svc.require_slot(db, user)
    return svc.preview(db, body.model_dump())

@router.post("/complete")
def complete(body: Configuration, db=Depends(get_db), user=Depends(require_authenticated_csrf), design_db=Depends(get_design_db)):
    result = svc.complete(db, user, body.model_dump())
    if design_enabled():
        from ..services import onboarding_service
        cfg = result["configuration"]
        result.update(onboarding_service.complete(design_db, user.user_id, user.participant_id, cfg.get("frontier_id", cfg["core_id"]), cfg["theme_ids"], cfg["reason"], confirmed_preview={**cfg, "personalized": {**cfg["personalized"], "expected_return": cfg["personalized"].get("expected_return")}, "risk_comparison": cfg.get("risk_comparison") or {"as_of": None, "method": None}}))
    return result
