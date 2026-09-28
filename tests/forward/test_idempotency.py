"""멱등성 테스트: 같은 작업을 반복해도 결과가 같아야 한다.

운용 기록은 매일 자동으로 돌고, 실패하면 다시 돌린다. 재실행이 행을 늘리거나
금액을 바꾸면 수익률이 전부 틀어지므로, 이 성질은 이 역할의 핵심 요구사항이다.

합성 가격 + 임시 DB 로 동작한다(네트워크·스냅샷 불필요).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.forward.accounts import ensure_personal_accounts, record_target, versions_from_cfg
from src.forward.db import connect, init_db
from src.forward.execution import create_orders, current_weights as _current, execute_pending
from src.forward.ledger import valuate
from src.forward.participants import add_participant
from src.forward.prices import CORE_IDS, theme_asset_id, upsert_prices
from src.forward.themes import register_themes

CFG = {
    "forward_test": {
        "timezone": "Asia/Seoul", "initial_nav": 100.0, "initial_capital_krw": 100000000.0,
        "benchmark_version": "CORE_V0.3", "theme_universe_version": "THEME_UNIVERSE_V0.1",
        "risk_model_version": "RISK_TEST", "execution_rule_version": "NEXT_AVAILABLE_CLOSE_V0",
        "stale_price_days": 14,
        "costs": {"trading_cost_bps": 5, "slippage_bps": 0, "fx_cost_bps": 0},
    }
}
THEMES = ["semiconductor", "ai"]
CORE_W = {a: 0.105 for a in CORE_IDS}
CORE_W["cash"] = 1.0 - sum(CORE_W.values())

ASOF = "2025-06-30"
LEDGER_TABLES = ("orders", "trades", "holdings_daily", "nav_daily")


def _prices(n_days=400, seed=7):
    idx = pd.bdate_range("2024-01-02", periods=n_days)
    rng = np.random.default_rng(seed)
    panel = {a: pd.Series(100 * np.cumprod(1 + rng.normal(0.0004, 0.01, n_days)), index=idx)
             for a in list(CORE_IDS) + [theme_asset_id(t) for t in THEMES]}
    return pd.DataFrame(panel)


@pytest.fixture()
def con(tmp_path):
    c = connect(tmp_path / "idem.db")
    init_db(c)
    register_themes(c, {"universe_version": "THEME_UNIVERSE_V0.1", "themes": [
        {"theme_id": t, "display_name": t, "theme_type": "theme", "ticker": "T",
         "market": "US", "currency": "USD", "active": True,
         "valid_from": "2024-01-01", "valid_to": None,
         "universe_version": "THEME_UNIVERSE_V0.1"} for t in THEMES]})
    upsert_prices(c, _prices(), "synthetic")
    return c


@pytest.fixture()
def account(con):
    """참가자 1명 + core 계좌 + 목표 비중."""
    pid = add_participant(con, "IDEM", "2024-01-02", "CORE_V0.3")
    core_id, _personal_id = ensure_personal_accounts(con, pid, "2024-01-02", CFG, "CORE_V0.3")
    record_target(con, core_id, CORE_W, ASOF, "core", versions_from_cfg(CFG),
                  "CORE_V0.3", participant_id=pid)
    con.commit()
    return core_id


def _counts(con) -> dict:
    return {t: con.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
            for t in LEDGER_TABLES}


def _nav_rows(con, aid) -> list[tuple]:
    return [(r["date"], float(r["nav"]), float(r["cash_balance"]), r["nav_status"])
            for r in con.execute(
                "SELECT date, nav, cash_balance, nav_status FROM nav_daily"
                " WHERE account_id = ? ORDER BY date", (aid,)).fetchall()]


def _run_once(con, aid):
    """하루치 처리: 체결 → 평가."""
    ft = CFG["forward_test"]
    execute_pending(con, aid, ASOF, float(ft["costs"]["trading_cost_bps"]),
                    ft["benchmark_version"])
    result = valuate(con, aid, ASOF, versions_from_cfg(CFG),
                     float(ft["initial_capital_krw"]), int(ft["stale_price_days"]))
    con.commit()
    return result


def _place_initial_orders(con, aid):
    ft = CFG["forward_test"]
    return create_orders(con, aid, CORE_W, f"{ASOF}T00:00:00+00:00", ASOF,
                         ft["benchmark_version"], kind="INITIAL")


# --------------------------------------------------------------------------
# 1. 평가(valuate) 멱등성
# --------------------------------------------------------------------------

def test_valuate_재실행시_행이_늘지_않는다(con, account):
    _place_initial_orders(con, account)
    first = _run_once(con, account)
    assert first["status"] == "OK"
    counts_1 = _counts(con)
    nav_1 = _nav_rows(con, account)

    for _ in range(3):
        _run_once(con, account)

    assert _counts(con) == counts_1, "재실행이 행 수를 바꿨다"
    assert _nav_rows(con, account) == nav_1, "재실행이 금액을 바꿨다"


def test_같은_날짜_NAV는_한_행만(con, account):
    _place_initial_orders(con, account)
    _run_once(con, account)
    _run_once(con, account)
    n = con.execute("SELECT COUNT(*) c FROM nav_daily WHERE account_id = ? AND date = ?",
                    (account, ASOF)).fetchone()["c"]
    assert n == 1


def test_보유_스냅샷도_자산당_한_행(con, account):
    _place_initial_orders(con, account)
    _run_once(con, account)
    _run_once(con, account)
    dup = con.execute(
        "SELECT asset_id, COUNT(*) c FROM holdings_daily"
        " WHERE account_id = ? AND date = ? GROUP BY asset_id HAVING COUNT(*) > 1",
        (account, ASOF)).fetchall()
    assert not dup, f"중복 보유 행: {[dict(r) for r in dup]}"


# --------------------------------------------------------------------------
# 2. 체결(execute_pending) 멱등성
# --------------------------------------------------------------------------

def test_체결은_한_번만_일어난다(con, account):
    _place_initial_orders(con, account)
    ft = CFG["forward_test"]
    filled_1 = execute_pending(con, account, ASOF, float(ft["costs"]["trading_cost_bps"]),
                               ft["benchmark_version"])
    con.commit()
    assert len(filled_1) > 0

    filled_2 = execute_pending(con, account, ASOF, float(ft["costs"]["trading_cost_bps"]),
                               ft["benchmark_version"])
    con.commit()
    assert filled_2 == [], "이미 체결된 주문이 다시 체결됐다"
    assert con.execute("SELECT COUNT(*) c FROM trades").fetchone()["c"] == len(filled_1)


def test_대기중인_주문이_남지_않는다(con, account):
    _place_initial_orders(con, account)
    _run_once(con, account)
    pending = con.execute(
        "SELECT COUNT(*) c FROM orders WHERE status = 'pending'").fetchone()["c"]
    assert pending == 0


# --------------------------------------------------------------------------
# 3. 회계 항등식 — 재실행해도 유지
# --------------------------------------------------------------------------

def test_회계_항등식이_유지된다(con, account):
    _place_initial_orders(con, account)
    for _ in range(3):
        _run_once(con, account)
    nav = con.execute("SELECT nav, cash_balance FROM nav_daily WHERE account_id = ?"
                      " AND date = ?", (account, ASOF)).fetchone()
    mv = con.execute("SELECT COALESCE(SUM(market_value), 0) s FROM holdings_daily"
                     " WHERE account_id = ? AND date = ?", (account, ASOF)).fetchone()["s"]
    gap = abs(float(mv) + float(nav["cash_balance"]) - float(nav["nav"]))
    assert gap < 1e-6, f"자산 + 현금 != NAV (차이 {gap})"


def test_거래비용이_중복_차감되지_않는다(con, account):
    _place_initial_orders(con, account)
    _run_once(con, account)
    cost_1 = con.execute("SELECT SUM(transaction_cost) s FROM trades").fetchone()["s"]
    for _ in range(3):
        _run_once(con, account)
    cost_2 = con.execute("SELECT SUM(transaction_cost) s FROM trades").fetchone()["s"]
    assert cost_1 == cost_2


# --------------------------------------------------------------------------
# 4. 주문 생성 멱등성
# --------------------------------------------------------------------------

def test_주문_생성을_두_번_호출해도_대기_주문이_중복되지_않는다(con, account):
    """create_orders 가 같은 계좌·자산·효력일의 pending 주문을 다시 만들지 않는다.

    (2026-09-28 변경) 예전에는 중복 방지를 호출부 책임으로 뒀지만, 배치를 다시
    돌리는 것이 정상 운영인 이상 생성 지점에서 막는 것이 맞다. 체결·취소된
    주문은 판정에서 빠지므로 다음 달 재조정은 그대로 가능하다.
    """
    _place_initial_orders(con, account)
    n1 = con.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"]
    assert n1 > 0
    _place_initial_orders(con, account)
    n2 = con.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"]
    assert n2 == n1


def test_체결_후에는_같은_자산에_다시_주문할_수_있다(con, account):
    """중복 방지가 다음 리밸런싱을 막아서는 안 된다."""
    _place_initial_orders(con, account)
    _run_once(con, account)
    executed = con.execute("SELECT COUNT(*) c FROM orders"
                           " WHERE status='executed'").fetchone()["c"]
    assert executed > 0
    n_before = con.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"]
    _place_initial_orders(con, account)
    n_after = con.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"]
    assert n_after > n_before


# --------------------------------------------------------------------------
# 5. 전량 매도 후 보유 행 정리
# --------------------------------------------------------------------------

def _sell_one_to_zero(con, account):
    """보유 자산 하나를 목표 0 으로 두고 같은 날짜에 전량 매도시킨다.

    execute_pending 은 주문이 아니라 portfolio_targets 의 weights_json 으로
    수량을 정한다. 같은 effective_date 에 목표 행을 새로 넣으면 어느 행이
    선택될지 불확정이므로, 기존 행을 갱신한다.
    """
    import json as _json
    ft = CFG["forward_test"]
    asset = con.execute("SELECT asset_id FROM holdings_daily WHERE account_id = ?"
                        " AND date = ? ORDER BY asset_id LIMIT 1",
                        (account, ASOF)).fetchone()["asset_id"]
    w = dict(CORE_W)
    w[asset] = 0.0
    con.execute("UPDATE portfolio_targets SET weights_json = ? WHERE account_id = ?"
                " AND effective_date = ?", (_json.dumps(w), account, ASOF))
    con.commit()
    create_orders(con, account, w, f"{ASOF}T00:00:00+00:00", ASOF,
                  ft["benchmark_version"], kind="REBALANCE",
                  baseline=_current(con, account, ASOF))
    _run_once(con, account)
    return asset


def test_전량_매도한_자산은_보유_행이_남지_않는다(con, account):
    """valuate 는 그날 보유를 통째로 다시 쓴다.

    INSERT OR REPLACE 만 하면 더 이상 보유하지 않는 자산의 예전 행이 남고,
    같은 날짜를 재평가할 때 Sigma(weight) 에 유령 자산이 섞여 항등식이 깨진다.
    (2026-09-28: 제거된 테마를 목표 0 으로 매도하면서 드러난 버그)
    """
    _place_initial_orders(con, account)
    _run_once(con, account)
    asset = _sell_one_to_zero(con, account)

    q = con.execute("SELECT COALESCE(SUM(quantity), 0) q FROM trades WHERE account_id = ?"
                    " AND asset_id = ?", (account, asset)).fetchone()["q"]
    assert abs(q) < 1e-9, f"전량 매도되지 않았다 (잔량 {q})"
    left = con.execute("SELECT COUNT(*) c FROM holdings_daily WHERE account_id = ?"
                       " AND date = ? AND asset_id = ?",
                       (account, ASOF, asset)).fetchone()["c"]
    assert left == 0, "전량 매도한 자산의 보유 행이 남아 있다"


def test_전량_매도_후에도_회계_항등식이_유지된다(con, account):
    _place_initial_orders(con, account)
    _run_once(con, account)
    _sell_one_to_zero(con, account)

    row = con.execute("SELECT SUM(weight) s FROM holdings_daily WHERE account_id = ?"
                      " AND date = ?", (account, ASOF)).fetchone()
    nav = con.execute("SELECT nav, cash_balance FROM nav_daily WHERE account_id = ?"
                      " AND date = ?", (account, ASOF)).fetchone()
    identity = float(row["s"]) + float(nav["cash_balance"]) / float(nav["nav"])
    assert abs(identity - 1.0) < 1e-6, f"항등식 위반: {identity}"


def test_다른_자산의_보유_행은_그대로_남는다(con, account):
    """통째로 다시 쓰는 방식이 멀쩡한 자산까지 지우면 안 된다."""
    _place_initial_orders(con, account)
    _run_once(con, account)
    before = con.execute("SELECT COUNT(*) c FROM holdings_daily WHERE account_id = ?"
                         " AND date = ?", (account, ASOF)).fetchone()["c"]
    _sell_one_to_zero(con, account)
    after = con.execute("SELECT COUNT(*) c FROM holdings_daily WHERE account_id = ?"
                        " AND date = ?", (account, ASOF)).fetchone()["c"]
    assert after == before - 1, f"{before} -> {after}: 매도한 자산 하나만 빠져야 한다"
