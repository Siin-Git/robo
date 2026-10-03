"""월간 리밸런싱 주문 생성 규칙.

팀 합의(2026-09-28):
  1. 개인 계좌도 실제 보유 비중 기준으로 교정한다(직전 목표 기준 아님).
  2. 목표에서 빠진 테마는 목표 0 으로 매도한다.
  3. 체결 전에 배치를 다시 돌려도 대기 주문이 중복되지 않는다.
"""
import sqlite3

import pytest

from src.forward.db import init_db
from src.forward.execution import create_orders

BAND = {"type": "relative", "threshold": 0.10, "min_absolute": 0.0}
SUBMIT = "2026-09-30T23:59:59+00:00"
EFFECTIVE = "2026-10-01"


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


def _orders(con, target, baseline, band=None, effective=EFFECTIVE):
    return create_orders(con, "ACC1", target, SUBMIT, effective, "CORE_V0.3", "P001",
                         kind="CORE_REBALANCE", baseline=baseline, band=band)


def _rows(con):
    return {r["asset_id"]: r for r in con.execute(
        "SELECT asset_id, side, target_weight, status FROM orders")}


# --------------------------------------------------------------------------
# 1. 제거된 테마 매도
# --------------------------------------------------------------------------

def test_목표에서_빠진_테마는_목표_0으로_매도한다(con):
    target = {"us_equity": 0.60, "cash": 0.40}          # theme:ai 가 사라졌다
    baseline = {"us_equity": 0.60, "theme:ai": 0.075}   # 실제로는 보유 중
    _orders(con, target, baseline)
    rows = _rows(con)
    assert "theme:ai" in rows, "제거된 테마의 매도 주문이 없다"
    assert rows["theme:ai"]["side"] == "sell"
    assert rows["theme:ai"]["target_weight"] == pytest.approx(0.0)


def test_제거된_테마는_밴드에_걸리지_않는다(con):
    """상대 밴드는 목표 x threshold 라서 목표 0 이면 밴드가 0 이다."""
    target = {"us_equity": 0.60, "cash": 0.40}
    baseline = {"us_equity": 0.60, "theme:ai": 0.001}   # 아주 작게 남아 있어도
    _orders(con, target, baseline, band=BAND)
    assert "theme:ai" in _rows(con)


def test_두_테마가_동시에_빠져도_각각_매도한다(con):
    target = {"us_equity": 0.60, "cash": 0.40}
    baseline = {"us_equity": 0.60, "theme:ai": 0.075, "theme:nuclear": 0.075}
    _orders(con, target, baseline, band=BAND)
    rows = _rows(con)
    assert {"theme:ai", "theme:nuclear"} <= set(rows)
    assert all(rows[t]["side"] == "sell" for t in ("theme:ai", "theme:nuclear"))


def test_baseline이_없으면_매도할_것도_없다(con):
    """최초 편입에는 보유가 없으므로 목표 0 자산이 생기지 않는다."""
    oids = _orders(con, {"us_equity": 0.60, "cash": 0.40}, None)
    assert len(oids) == 1
    assert set(_rows(con)) == {"us_equity"}


def test_cash는_주문을_만들지_않는다(con):
    _orders(con, {"us_equity": 0.60, "cash": 0.40}, {"us_equity": 0.30, "cash": 0.70})
    assert "cash" not in _rows(con)


# --------------------------------------------------------------------------
# 2. 보유 비중 기준 교정
# --------------------------------------------------------------------------

def test_보유_비중_기준이면_드리프트를_교정한다(con):
    """목표는 그대로인데 가격이 올라 비중이 벌어진 경우."""
    target = {"us_equity": 0.20, "cash": 0.80}
    holdings = {"us_equity": 0.26}      # 밴드(18~22%) 밖
    oids = _orders(con, target, holdings, band=BAND)
    assert len(oids) == 1
    assert _rows(con)["us_equity"]["side"] == "sell"


def test_직전_목표_기준이었다면_놓쳤을_드리프트다(con):
    """같은 상황에서 baseline 을 직전 목표로 주면 주문이 생기지 않는다.

    이 테스트는 기준을 바꾼 이유를 고정한다. 목표가 안 변했으면 편차가 0 이라
    가격 변동으로 생긴 드리프트를 영원히 교정하지 않는다.
    """
    target = {"us_equity": 0.20, "cash": 0.80}
    prev_target = {"us_equity": 0.20, "cash": 0.80}
    assert _orders(con, target, prev_target, band=BAND) == []


# --------------------------------------------------------------------------
# 3. 체결 전 주문 중복
# --------------------------------------------------------------------------

def test_같은_배치를_두_번_돌려도_대기_주문이_늘지_않는다(con):
    target = {"us_equity": 0.20, "korea_equity": 0.10, "cash": 0.70}
    baseline = {"us_equity": 0.30, "korea_equity": 0.02}
    first = _orders(con, target, baseline, band=BAND)
    assert len(first) == 2
    second = _orders(con, target, baseline, band=BAND)
    assert second == [], "중복 주문이 생성됐다"
    assert con.execute("SELECT COUNT(*) AS n FROM orders").fetchone()["n"] == 2


def test_중복_주문은_이벤트도_남기지_않는다(con):
    target = {"us_equity": 0.20, "cash": 0.80}
    baseline = {"us_equity": 0.30}
    _orders(con, target, baseline)
    n1 = con.execute("SELECT COUNT(*) AS n FROM events"
                     " WHERE event_type='ORDER_CREATED'").fetchone()["n"]
    _orders(con, target, baseline)
    n2 = con.execute("SELECT COUNT(*) AS n FROM events"
                     " WHERE event_type='ORDER_CREATED'").fetchone()["n"]
    assert n1 == n2 == 1


def test_체결된_주문은_중복_판정에서_빠진다(con):
    """다음 달 같은 자산을 다시 조정할 수 있어야 한다."""
    target = {"us_equity": 0.20, "cash": 0.80}
    _orders(con, target, {"us_equity": 0.30})
    con.execute("UPDATE orders SET status='executed'")
    con.commit()
    again = _orders(con, target, {"us_equity": 0.30})
    assert len(again) == 1, "체결이 끝났는데도 새 주문을 막았다"


def test_다른_효력일이면_별도_주문이_생긴다(con):
    target = {"us_equity": 0.20, "cash": 0.80}
    _orders(con, target, {"us_equity": 0.30}, effective="2026-10-01")
    _orders(con, target, {"us_equity": 0.30}, effective="2026-11-01")
    assert con.execute("SELECT COUNT(*) AS n FROM orders").fetchone()["n"] == 2


def test_취소된_주문은_중복_판정에서_빠진다(con):
    target = {"us_equity": 0.20, "cash": 0.80}
    _orders(con, target, {"us_equity": 0.30})
    con.execute("UPDATE orders SET status='cancelled'")
    con.commit()
    assert len(_orders(con, target, {"us_equity": 0.30})) == 1


def test_계좌가_다르면_서로_막지_않는다(con):
    con.execute("INSERT INTO accounts (account_id, participant_id, account_type, shadow_name,"
                " benchmark_version, inception_date, initial_capital_krw, status, created_at)"
                " VALUES ('ACC2', 'P002', 'personal', NULL, 'CORE_V0.3', '2026-09-01',"
                " 100000000, 'active', '2026-09-01T00:00:00+00:00')")
    con.commit()
    target = {"us_equity": 0.20, "cash": 0.80}
    _orders(con, target, {"us_equity": 0.30})
    create_orders(con, "ACC2", target, SUBMIT, EFFECTIVE, "CORE_V0.3", "P002",
                  kind="CORE_REBALANCE", baseline={"us_equity": 0.30})
    assert con.execute("SELECT COUNT(DISTINCT account_id) AS n FROM orders"
                       ).fetchone()["n"] == 2
    assert con.execute("SELECT COUNT(*) AS n FROM orders").fetchone()["n"] == 2


def test_제거된_테마_매도도_중복되지_않는다(con):
    target = {"us_equity": 0.60, "cash": 0.40}
    baseline = {"us_equity": 0.60, "theme:ai": 0.075}
    _orders(con, target, baseline, band=BAND)
    _orders(con, target, baseline, band=BAND)
    assert con.execute("SELECT COUNT(*) AS n FROM orders WHERE asset_id='theme:ai'"
                       ).fetchone()["n"] == 1


# --------------------------------------------------------------------------
# plan_orders: 드라이런과 실제 실행이 같은 결론을 내는가
# --------------------------------------------------------------------------

def test_plan_orders가_create_orders와_일치한다(con):
    """미리 본 것과 실제가 다르면 드라이런의 의미가 없다."""
    from src.forward.execution import plan_orders
    target = {"us_equity": 0.20, "korea_equity": 0.10, "gold": 0.05, "cash": 0.65}
    baseline = {"us_equity": 0.21,      # 밴드 안
                "korea_equity": 0.13,   # 밴드 밖
                "gold": 0.05,           # 변화 없음
                "theme:ai": 0.04}       # 목표에서 빠짐 -> 매도
    planned = {r["asset"]: r["action"] for r in plan_orders(target, baseline, BAND)}
    _orders(con, target, baseline, band=BAND)
    actual = set(_rows(con))
    assert {a for a, act in planned.items() if act == "order"} == actual


def test_plan_orders는_DB를_보지_않는다():
    """드라이런이 어떤 DB 상태에서도 같은 판단을 내려야 한다."""
    from src.forward.execution import plan_orders
    rows = plan_orders({"us_equity": 0.20, "cash": 0.80}, {"us_equity": 0.30}, BAND)
    assert [r["action"] for r in rows] == ["order"]


def test_plan_orders가_세_가지_판단을_구분한다():
    from src.forward.execution import plan_orders
    target = {"us_equity": 0.20, "korea_equity": 0.10, "gold": 0.05, "cash": 0.65}
    baseline = {"us_equity": 0.21, "korea_equity": 0.13, "gold": 0.05}
    by_asset = {r["asset"]: r for r in plan_orders(target, baseline, BAND)}
    assert by_asset["us_equity"]["action"] == "band"
    assert by_asset["korea_equity"]["action"] == "order"
    assert by_asset["gold"]["action"] == "unchanged"
    assert by_asset["korea_equity"]["side"] == "sell"
    assert by_asset["korea_equity"]["drift"] == pytest.approx(-0.03)


def test_밴드가_없으면_band_판단이_나오지_않는다():
    from src.forward.execution import plan_orders
    rows = plan_orders({"us_equity": 0.20, "cash": 0.80}, {"us_equity": 0.21}, None)
    assert [r["action"] for r in rows] == ["order"]


def test_드라이런은_아무것도_쓰지_않는다(con, tmp_path):
    """--dry-run 이 한 행이라도 남기면 미리보기가 아니다."""
    import src.forward.run_monthly as rm
    tables = ("orders", "trades", "holdings_daily", "nav_daily", "events",
              "portfolio_targets", "model_versions", "scheduled_jobs")

    def snapshot():
        return {t: con.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
                for t in tables}

    cfg = {"forward_test": {"benchmark_version": "CORE_V0.3",
                            "core_rebalance": {"frequency": "monthly", "band": BAND}},
           "frozen_dir": "outputs/frozen/CORE_V0.3"}
    before = snapshot()
    try:
        rm._dry_run_monthly(con, cfg, "2026", "09", "2026-09-30", risk_only=True)
    except Exception:
        pass          # 데이터가 없어 중단되어도 쓰기는 없어야 한다
    assert snapshot() == before
