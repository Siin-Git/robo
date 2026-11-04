"""리밸런싱 밴드(상대 기준) 테스트.

합의: 목표 비중 20%, threshold 0.10 -> 18~22% 안이면 주문을 만들지 않는다.
"""
import sqlite3

import pytest

from src.forward.db import init_db
from src.forward.execution import create_orders, within_band

BAND = {"type": "relative", "threshold": 0.10, "min_absolute": 0.0}


# --------------------------------------------------------------------------
# 순수 함수: 경계값
# --------------------------------------------------------------------------

@pytest.mark.parametrize("current, inside", [
    (0.20, True),    # 목표와 동일
    (0.18, True),    # 하단 경계 포함
    (0.22, True),    # 상단 경계 포함
    (0.199, True),
    (0.2201, False),  # 밴드 밖
    (0.1799, False),
    (0.15, False),
    (0.30, False),
])
def test_상대밴드_20퍼센트_목표(current, inside):
    assert within_band(0.20, current, BAND) is inside


def test_목표가_0이면_항상_조정한다():
    """자산을 빼는 주문(목표 0)은 상대 밴드가 0 이므로 막히지 않는다."""
    assert within_band(0.0, 0.03, BAND) is False
    assert within_band(0.0, 0.0, BAND) is True  # 이미 0 이면 애초에 편차가 없다


def test_밴드가_없으면_항상_밖으로_본다():
    assert within_band(0.20, 0.2000001, None) is False
    assert within_band(0.20, 0.2000001, {}) is False


def test_min_absolute를_주면_그_폭까지_무시한다():
    band = {"type": "relative", "threshold": 0.10, "min_absolute": 0.01}
    # 목표 2% -> 상대 밴드는 0.2%p 뿐이지만 min_absolute 1%p 가 우선한다.
    assert within_band(0.02, 0.025, band) is True
    assert within_band(0.02, 0.035, band) is False


def test_절대밴드_타입도_지원한다():
    band = {"type": "absolute", "threshold": 0.02}
    assert within_band(0.20, 0.215, band) is True
    assert within_band(0.20, 0.23, band) is False


# --------------------------------------------------------------------------
# create_orders 통합
# --------------------------------------------------------------------------

@pytest.fixture()
def con():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    c.execute("INSERT INTO accounts (account_id, participant_id, account_type, shadow_name,"
              " benchmark_version, inception_date, initial_capital_krw, status, created_at)"
              " VALUES ('ACC1', 'P001', 'personal', NULL, 'CORE_V0.3', '2026-09-01',"
              " 100000000, 'active', '2026-09-01T00:00:00+00:00')")
    c.commit()
    return c


def _orders(con, target, baseline, band=BAND):
    return create_orders(con, "ACC1", target, "2026-09-30T23:59:59+00:00", "2026-10-01",
                         "CORE_V0.3", "P001", kind="CORE_REBALANCE",
                         baseline=baseline, band=band)


def test_밴드_안의_편차는_주문을_만들지_않는다(con):
    # 목표 20%, 현재 21% -> 18~22% 안
    oids = _orders(con, {"us_equity": 0.20, "cash": 0.0}, {"us_equity": 0.21})
    assert oids == []
    assert con.execute("SELECT COUNT(*) AS n FROM orders").fetchone()["n"] == 0


def test_밴드_밖의_편차는_주문을_만든다(con):
    # 목표 20%, 현재 25% -> 22% 초과
    oids = _orders(con, {"us_equity": 0.20, "cash": 0.0}, {"us_equity": 0.25})
    assert len(oids) == 1
    row = con.execute("SELECT side, target_weight FROM orders").fetchone()
    assert row["side"] == "sell"
    assert row["target_weight"] == pytest.approx(0.20)


def test_밴드_밖은_목표_비중으로_복귀한다(con):
    """밴드를 벗어나면 경계(22%)가 아니라 목표(20%)까지 되돌린다."""
    _orders(con, {"us_equity": 0.20, "cash": 0.0}, {"us_equity": 0.30})
    assert con.execute("SELECT target_weight FROM orders").fetchone()["target_weight"] \
        == pytest.approx(0.20)


def test_자산별로_따로_판단한다(con):
    target = {"us_equity": 0.20, "korea_equity": 0.10, "gold": 0.05, "cash": 0.0}
    baseline = {"us_equity": 0.21,   # 밴드 안 (18~22)
                "korea_equity": 0.13,  # 밴드 밖 (9~11)
                "gold": 0.05}          # 편차 없음
    oids = _orders(con, target, baseline)
    assets = [r["asset_id"] for r in con.execute(
        "SELECT asset_id FROM orders ORDER BY asset_id").fetchall()]
    assert assets == ["korea_equity"]
    assert len(oids) == 1


def test_밴드를_주지_않으면_기존_동작을_유지한다(con):
    oids = _orders(con, {"us_equity": 0.20, "cash": 0.0}, {"us_equity": 0.21}, band=None)
    assert len(oids) == 1


def test_최초_편입에는_밴드를_적용하지_않는다(con):
    """baseline None(보유 0에서 시작)은 전 자산을 사야 하므로 밴드로 막지 않는다."""
    oids = create_orders(con, "ACC1", {"us_equity": 0.20, "korea_equity": 0.10, "cash": 0.0},
                         "2026-09-30T23:59:59+00:00", "2026-10-01", "CORE_V0.3", "P001",
                         kind="INITIAL", baseline=None, band=BAND)
    assert len(oids) == 2


def test_밴드로_걸러진_자산은_이벤트도_남지_않는다(con):
    _orders(con, {"us_equity": 0.20, "cash": 0.0}, {"us_equity": 0.21})
    assert con.execute("SELECT COUNT(*) AS n FROM events WHERE event_type='ORDER_CREATED'"
                       ).fetchone()["n"] == 0


def test_config의_밴드_설정이_상대_10퍼센트다():
    from src.forward.config import load_forward_config
    band = load_forward_config()["forward_test"]["core_rebalance"]["band"]
    assert band["type"] == "relative"
    assert float(band["threshold"]) == pytest.approx(0.10)
