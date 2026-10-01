"""static_weights: 드라이런과 실제 실행이 같은 비중을 본다.

예전에는 run_monthly 의 미리보기가 모든 그림자를 frozen 으로 취급해
"24건을 만들겠다" 고 예고하고 실제로는 26건을 만들었다. 미리보기와 결과가
다르면 run_daily_task.bat 이 계획을 먼저 기록하는 의미가 없다.
"""
import pytest

FROZEN = {"us_equity": 0.3, "korea_equity": 0.2, "gold": 0.1, "cash": 0.4}


def test_core는_frozen을_그대로_쓴다():
    from src.forward.accounts import static_weights
    assert static_weights("core", None, {}, FROZEN) == FROZEN


def test_core_v03_그림자도_frozen이다():
    from src.forward.accounts import static_weights
    assert static_weights("shadow", "core_v03", {}, FROZEN) == FROZEN


def test_equal_weight은_균등이고_frozen과_다르다():
    from src.forward.accounts import static_weights
    from src.forward.prices import CORE_IDS
    w = static_weights("shadow", "equal_weight", {}, FROZEN)
    assert w != FROZEN, "그림자를 frozen 으로 취급하면 미리보기가 어긋난다"
    assert w["cash"] == 0.0
    assert len(w) == len(CORE_IDS) + 1
    assert all(abs(v - 1 / len(CORE_IDS)) < 1e-12 for k, v in w.items() if k != "cash")


def test_모르는_그림자는_조용히_넘어가지_않는다():
    from src.forward.accounts import static_weights
    with pytest.raises(ValueError):
        static_weights("shadow", "unknown_benchmark", {}, FROZEN)


def test_반환값이_원본을_공유하지_않는다():
    """호출부가 w 를 고쳐도 frozen 원본이 바뀌면 안 된다."""
    from src.forward.accounts import static_weights
    w = static_weights("core", None, {}, FROZEN)
    w["us_equity"] = 999
    assert FROZEN["us_equity"] == 0.3
