"""Portfolio routes (owner-scoped; core is visible to any login)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..authz import enforce_owner, get_current_user
from ..dependencies import get_db
from ..services import portfolio_service as svc

router = APIRouter(tags=["portfolios"])


@router.get("/participants/{participant_id}/portfolio",
            summary="Current personalized portfolio")
def get_portfolio(participant_id: str, db=Depends(get_db),
                  user=Depends(get_current_user)):
    enforce_owner(user, participant_id)
    return svc.personalized(db, participant_id)


@router.get("/participants/{participant_id}/portfolio/comparison",
            summary="Core vs personalized comparison")
def get_comparison(participant_id: str, db=Depends(get_db),
                   user=Depends(get_current_user)):
    enforce_owner(user, participant_id)
    return svc.comparison(db, participant_id)


@router.get("/portfolio/core", summary="Frozen CORE_V0.3 portfolio")
def get_core(db=Depends(get_db), user=Depends(get_current_user)):
    return svc.core(db)
