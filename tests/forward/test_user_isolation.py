"""사용자별 독립성 테스트 (다인원 로그인 시연 전제).

"forward 가 돈다" 만으로는 부족하다. 같은 DB 에서 여러 사용자가 동시에 운용될 때
- 계좌·주문·체결·보유·NAV 가 user(participant) 별로 분리되어 쌓이고,
- 한 사람의 목표 비중/재실행이 다른 사람의 기록을 바꾸지 않는다

는 것을 이 파일이 보장한다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.forward.accounts import ensure_personal_accounts, record_target, versions_from_cfg
from src.forward.db import connect, init_db
from src.forward.execution import create_orders, execute_pending
from src.forward.ledger import valuate
from src.forward.participants import add_participant
from src.forward.prices import CORE_IDS, upsert_prices

CFG = {
    "forward_test": {
        "timezone": "Asia/Seoul", "initial_nav": 100.0, "initial_capital_krw": 100000000.0,
        "benchmark_version": "CORE_V0.3", "theme_universe_version": "THEME_UNIVERSE_V0.1",
        "risk_model_version": "RISK_TEST", "execution_rule_version": "NEXT_AVAILABLE_CLOSE_V0",
        "stale_price_days": 14,
        "costs": {"trading_cost_bps": 5, "slippage_bps": 0, "fx_cost_bps": 0},
    }
}
FT = CFG["forward_test"]
ASOF = "2025-06-30"
N_USERS = 13  # 시연 인원과 비슷한 규모. 시연 인원수와 연동되지는 않는다

# 사용자마다 다른 목표 비중(같은 비중이면 분리 여부를 못 본다)
def _weights(i: int) -> dict:
    tilt = 0.02 * (i % 4)
    w = {a: 0.10 for a in CORE_IDS}
    first = list(CORE_IDS)[0]
    w[first] = 0.10 + tilt
    w["cash"] = 1.0 - sum(w.values())
    return w


def _prices(n_days=400, seed=11):
    idx = pd.bdate_range("2024-01-02", periods=n_days)
    rng = np.random.default_rng(seed)
    return pd.DataFrame({a: pd.Series(
        100 * np.cumprod(1 + rng.normal(0.0004, 0.01, n_days)), index=idx) for a in CORE_IDS})


@pytest.fixture()
def con(tmp_path):
    c = connect(tmp_path / "isolation.db")
    init_db(c)
    upsert_prices(c, _prices(), "synthetic")
    return c


@pytest.fixture()
def users(con):
    """참가자 N 명 각각의 personal 계좌 + 서로 다른 목표 비중."""
    out = []
    for i in range(N_USERS):
        pid = add_participant(con, f"USER{i:02d}", "2024-01-02", "CORE_V0.3")
        _core, personal = ensure_personal_accounts(con, pid, "2024-01-02", CFG, "CORE_V0.3")
        w = _weights(i)
        record_target(con, personal, w, ASOF, "personal", versions_from_cfg(CFG),
                      "CORE_V0.3", participant_id=pid)
        out.append({"participant_id": pid, "account_id": personal, "weights": w})
    con.commit()
    return out


def _run(con, account_id, weights, kind="INITIAL"):
    create_orders(con, account_id, weights, f"{ASOF}T00:00:00+00:00", ASOF,
                  FT["benchmark_version"], kind=kind)
    execute_pending(con, account_id, ASOF, float(FT["costs"]["trading_cost_bps"]),
                    FT["benchmark_version"])
    res = valuate(con, account_id, ASOF, versions_from_cfg(CFG),
                  float(FT["initial_capital_krw"]), int(FT["stale_price_days"]))
    con.commit()
    return res


def _rows(con, table, account_id):
    return con.execute(f"SELECT COUNT(*) AS c FROM {table} WHERE account_id = ?",
                       (account_id,)).fetchone()["c"]


# --------------------------------------------------------------------------

def test_계좌가_참가자별로_하나씩_생긴다(con, users):
    assert len({u["account_id"] for u in users}) == N_USERS
    assert len({u["participant_id"] for u in users}) == N_USERS
    orphan = con.execute("SELECT COUNT(*) AS c FROM accounts WHERE account_type='personal'"
                         " AND participant_id IS NULL").fetchone()["c"]
    assert orphan == 0


def test_13명_모두_각자_기록이_쌓인다(con, users):
    for u in users:
        assert _run(con, u["account_id"], u["weights"])["status"] == "OK"
    for u in users:
        assert _rows(con, "orders", u["account_id"]) > 0
        assert _rows(con, "trades", u["account_id"]) > 0
        assert _rows(con, "holdings_daily", u["account_id"]) > 0
        assert _rows(con, "nav_daily", u["account_id"]) == 1
    # 다른 계좌의 행이 하나도 섞이지 않는다
    total = con.execute("SELECT COUNT(*) AS c FROM nav_daily").fetchone()["c"]
    assert total == N_USERS


def test_한_사람만_돌리면_나머지는_비어있다(con, users):
    target, other = users[0], users[1]
    _run(con, target["account_id"], target["weights"])
    for table in ("orders", "trades", "holdings_daily", "nav_daily"):
        assert _rows(con, table, other["account_id"]) == 0, table


def test_다른_사람을_돌려도_내_NAV는_변하지_않는다(con, users):
    me, other = users[0], users[5]
    _run(con, me["account_id"], me["weights"])
    before = con.execute("SELECT nav, cash_balance FROM nav_daily WHERE account_id = ?",
                         (me["account_id"],)).fetchone()
    _run(con, other["account_id"], other["weights"])
    after = con.execute("SELECT nav, cash_balance FROM nav_daily WHERE account_id = ?",
                        (me["account_id"],)).fetchone()
    assert float(after["nav"]) == pytest.approx(float(before["nav"]))
    assert float(after["cash_balance"]) == pytest.approx(float(before["cash_balance"]))


def test_목표_비중이_다르면_보유_비중도_사람마다_다르다(con, users):
    for u in users:
        _run(con, u["account_id"], u["weights"])
    first_asset = list(CORE_IDS)[0]
    got = {}
    for u in users:
        row = con.execute("SELECT weight FROM holdings_daily WHERE account_id = ?"
                          " AND asset_id = ? AND date = ?",
                          (u["account_id"], first_asset, ASOF)).fetchone()
        got[u["participant_id"]] = float(row["weight"])
    # 4가지 tilt 를 썼으므로 서로 다른 값이 최소 4개 있어야 한다
    assert len({round(v, 4) for v in got.values()}) >= 4
    # 각자 자기 목표 비중 근처에 있다
    for u in users:
        assert got[u["participant_id"]] == pytest.approx(u["weights"][first_asset], abs=0.01)


def test_이벤트가_participant_id로_구분된다(con, users):
    me, other = users[0], users[1]
    _run(con, me["account_id"], me["weights"])
    _run(con, other["account_id"], other["weights"])
    mine = con.execute("SELECT COUNT(*) AS c FROM events WHERE account_id = ?",
                       (me["account_id"],)).fetchone()["c"]
    theirs = con.execute("SELECT COUNT(*) AS c FROM events WHERE account_id = ?",
                         (other["account_id"],)).fetchone()["c"]
    assert mine > 0 and theirs > 0
    overlap = con.execute("SELECT COUNT(*) AS c FROM events WHERE account_id IN (?, ?)"
                          " AND account_id IS NULL", (me["account_id"],
                                                      other["account_id"])).fetchone()["c"]
    assert overlap == 0


def test_전원_재실행해도_행이_늘지_않는다(con, users):
    """다인원 시연 중 배치를 두 번 돌려도 기록이 중복되지 않는다."""
    for u in users:
        _run(con, u["account_id"], u["weights"])
    snap = {t: con.execute(f"SELECT COUNT(*) AS c FROM {t}").fetchone()["c"]
            for t in ("trades", "holdings_daily", "nav_daily")}
    for u in users:
        execute_pending(con, u["account_id"], ASOF,
                        float(FT["costs"]["trading_cost_bps"]), FT["benchmark_version"])
        valuate(con, u["account_id"], ASOF, versions_from_cfg(CFG),
                float(FT["initial_capital_krw"]), int(FT["stale_price_days"]))
    con.commit()
    again = {t: con.execute(f"SELECT COUNT(*) AS c FROM {t}").fetchone()["c"]
             for t in ("trades", "holdings_daily", "nav_daily")}
    assert again == snap
