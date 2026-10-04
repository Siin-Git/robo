from fastapi import APIRouter, Depends, Query
from ..authz import get_current_user
from ..services import strategy_service

router = APIRouter(prefix="/strategies", tags=["strategy research"])


@router.get("")
def catalog(user=Depends(get_current_user)):
    return strategy_service.catalog()


@router.get("/{strategy_id}")
def detail(strategy_id: str, variant: str | None = Query(default=None), user=Depends(get_current_user)):
    return strategy_service.detail(strategy_id, variant)
