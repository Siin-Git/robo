"""NAV engine: holdings valuation from the trade ledger (replay-safe)."""
from __future__ import annotations

import sqlite3

from .opening import assets as position_assets, cash as position_cash, opening
from .db import log_event
from .execution import holding_qty
from .prices import price_on_or_before


def cash_balance(con: sqlite3.Connection, account_id: str, asof: str,
                 initial_capital: float) -> float:
    return position_cash(con, account_id, asof, initial_capital)


def valuate(con: sqlite3.Connection, account_id: str, date: str, versions: dict,
            initial_capital: float, stale_days: int = 14) -> dict:
    """Value holdings at date; write holdings_daily + nav_daily. Returns summary."""
    from .competition import account_gate
    blocked, start_date = account_gate(con, account_id)
    if blocked or (start_date and date < start_date):
        return {"status": "NAV_INCOMPLETE", "reason": "competition not started for this valuation"}
    assets = position_assets(con, account_id, date)
    if not assets and not opening(con, account_id, date):
        # No executions yet: NAV anchor must only be created after first execution
        # (never backfill performance before inception fills).
        return {"status": "NAV_INCOMPLETE", "reason": "no executions yet"}
    mv_total, rows, stale = 0.0, [], False
    for a in assets:
        q = holding_qty(con, account_id, a, date)
        if abs(q) < 1e-12:
            continue
        px, px_date, is_stale = price_on_or_before(con, a, date, stale_days)
        if px is None:
            return {"status": "NAV_INCOMPLETE", "missing": a}
        stale = stale or is_stale
        rows.append((a, q, px))
        mv_total += q * px
    cash = cash_balance(con, account_id, date, initial_capital)
    nav = mv_total + cash
    if not (nav == nav) or nav in (float("inf"), float("-inf")) or nav <= 0:
        return {"status": "NAV_INCOMPLETE", "reason": "non-finite nav"}
    prev = con.execute("SELECT nav FROM nav_daily WHERE account_id = ? AND date < ?"
                       " ORDER BY date DESC LIMIT 1", (account_id, date)).fetchone()
    inception = con.execute("SELECT nav FROM nav_daily WHERE account_id = ?"
                            " ORDER BY date LIMIT 1", (account_id,)).fetchone()
    base0 = inception["nav"] if inception else nav
    # 항등식은 쓰기 전에 확인한다. 깨진 상태로 행을 남기면 안 된다.
    wsum = sum(r[1] * r[2] for r in rows) / nav
    if abs((wsum + cash / nav) - 1.0) > 1e-6:
        return {"status": "NAV_INCOMPLETE", "reason": "accounting identity broken"}
    # 전량 매도된 자산의 행이 남지 않도록 그날 보유를 통째로 다시 쓴다.
    # INSERT OR REPLACE 만 하면 더 이상 보유하지 않는 자산의 예전 행이 남고,
    # 같은 날짜를 재평가할 때 Σweight 에 유령 자산이 섞여 항등식이 깨진다.
    con.execute("DELETE FROM holdings_daily WHERE account_id = ? AND date = ?",
                (account_id, date))
    for a, q, px in rows:
        mvv = q * px
        con.execute("INSERT OR REPLACE INTO holdings_daily (account_id, date, asset_id,"
                    " quantity, price, market_value, weight) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (account_id, date, a, q, px, mvv, mvv / nav))
    daily_ret = (nav / prev["nav"] - 1.0) if prev else 0.0
    con.execute("INSERT OR REPLACE INTO nav_daily (account_id, date, nav, nav_base100,"
                " daily_return, cumulative_return, cash_balance, stale_price_flag, nav_status,"
                " benchmark_version, theme_universe_version, risk_model_version,"
                " execution_rule_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (account_id, date, nav, nav / base0 * 100.0, daily_ret, nav / base0 - 1.0,
                 cash, bool(stale),
                 "STALE_PRICE" if stale else "OK", versions["benchmark_version"],
                 versions["theme_universe_version"], versions["risk_model_version"],
                 versions["execution_rule_version"]))
    con.commit()
    # Preserve evidence on the existing valuation event: later price refreshes
    # must not turn fixture/replay NAV into forward performance.
    replay = con.execute("SELECT 1 FROM forward_state WHERE key='replay_run_id'").fetchone()
    synthetic = con.execute("SELECT 1 FROM prices_daily WHERE LOWER(source) LIKE ? AND date<=? LIMIT 1",
                            ("synthetic%", date)).fetchone()
    data_kind = "HISTORICAL_REPLAY" if replay else "TEST_FIXTURE" if synthetic else "FORWARD_SIMULATION"
    log_event(con, "NAV_CALCULATED", versions["benchmark_version"], None, account_id,
              {"date": date, "nav": nav, "data_kind": data_kind,
               "opening_run_id": (opening(con, account_id, date) or {}).get("run_id")})
    con.commit()
    return {"status": "STALE_PRICE" if stale else "OK", "nav": nav}


def nav_series(con: sqlite3.Connection, account_id: str) -> list[dict]:
    return [dict(r) for r in con.execute(
        "SELECT * FROM nav_daily WHERE account_id = ? ORDER BY date", (account_id,)).fetchall()]
