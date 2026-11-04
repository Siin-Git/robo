from fastapi import APIRouter, Depends, Query
from ..authz import get_current_user
from ..services import strategy_service

router = APIRouter(prefix="/strategies", tags=["strategy research"])


@router.get("")
def catalog(user=Depends(get_current_user)):
    return strategy_service.catalog()


@router.get("/frontier-comparison")
def frontier_comparison(user=Depends(get_current_user)):
    from ..services.strategy_frontier_service import comparison
    try:
        return comparison()
    except (ValueError, KeyError, OSError):
        from ..errors import ApiError
        raise ApiError("STRATEGY_COMPARISON_UNAVAILABLE", "모델 비교 계산에 필요한 원본 자료를 확인하지 못했습니다.", 503)


@router.get("/v8-frontier-comparison")
def v8_frontier_comparison(user=Depends(get_current_user)):
    from ..services.v8_frontier_service import comparison
    try:
        return comparison()
    except (ValueError, KeyError, OSError):
        from ..errors import ApiError
        raise ApiError("V8_COMPARISON_UNAVAILABLE", "V8 백테스트 비교 자료를 확인하지 못했습니다.", 503)


@router.get("/{strategy_id}")
def detail(strategy_id: str, variant: str | None = Query(default=None), user=Depends(get_current_user)):
    return strategy_service.detail(strategy_id, variant)
