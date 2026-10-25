from typing import Literal
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from ..authz import get_current_user
from ..design_workspace import get_design_db, require_design_csrf
from ..services import decision_service as svc
router = APIRouter(prefix="/me", tags=["decisions"])

class ChoiceBody(BaseModel):
    decision_id: str
    target_id: str
    action: Literal["KEEP", "ADJUST"]
    reason: str = Field(min_length=1, max_length=1024)
    request_key: str = Field(min_length=8, max_length=64)

@router.get("/decisions")
def decisions(db=Depends(get_design_db), user=Depends(get_current_user)):
    return svc.list_decisions(db, user.user_id)

@router.get("/decisions/{decision_id}/review")
def review(decision_id: str, db=Depends(get_design_db), user=Depends(get_current_user)):
    return svc.review(db, user.user_id, decision_id)

@router.get("/decisions/{decision_id}/verification")
def verification(decision_id: str, db=Depends(get_design_db), user=Depends(get_current_user)):
    from ..services.decision_verification_service import verification as read_verification
    return read_verification(db, user.user_id, decision_id)

@router.get("/portfolio/choices")
def choices(db=Depends(get_design_db), user=Depends(get_current_user)):
    return svc.choices(db, user.user_id)

@router.get("/decisions/{decision_id}/rehearsal")
def rehearsal(decision_id: str, period: str = Query(default="all", pattern=r"^(all|[0-9]{4})$"),
              initial_amount: int = Query(default=10_000_000, ge=10_000, le=1_000_000_000),
              db=Depends(get_design_db), user=Depends(get_current_user)):
    from ..services.rehearsal_service import rehearsal as read_rehearsal
    return read_rehearsal(db, user.user_id, decision_id, period, initial_amount)

@router.post("/portfolio/choices")
def choose(body: ChoiceBody, db=Depends(get_design_db), user=Depends(require_design_csrf)):
    return svc.choose(db, user.user_id, **body.model_dump())
