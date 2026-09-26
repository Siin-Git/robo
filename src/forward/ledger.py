"""NAV engine: holdings valuation from the trade ledger (replay-safe)."""
from __future__ import annotations

import sqlite3

from .db import log_event
from .execution import holding_qty
from .prices import price_on_or_before


def cash_balance(con: sqlite3.Connection, account_id: str, asof: str,
                 initial_capital: float) -> float:
    cash = initial_capital
    for r in con.execute("SELECT quantity, gross_value, transaction_cost FROM trades"
                         " WHERE account_id = ? AND execution_at <= ?",
                         (account_id, asof)).fetchall():
        if r["quantity"] > 0:
            cash -= r["gross_value"] + r["transaction_cost"]
        else:
            cash += r["gross_value"] - r["transaction_cost"]
    return cash


def valuate(con: sqlite3.Connection, account_id: str, date: str, versions: dict,
            initial_capital: float, stale_days: int = 14) -> dict:
    """Value holdings at date; write holdings_daily + nav_daily. Returns summary."""
    assets = [r["asset_id"] for r in con.execute(
        "SELECT DISTINCT asset_id FROM trades WHERE account_id = ? AND execution_at <= ?",
        (account_id, date)).fetchall()]
    if not assets:
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
    for a, q, px in rows:
        mvv = q * px
        con.execute("INSERT OR REPLACE INTO holdings_daily (account_id, date, asset_id,"
                    " quantity, price, market_value, weight) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (account_id, date, a, q, px, mvv, mvv / nav))
    wsum = sum(r[1] * r[2] for r in rows) / nav
    if abs((wsum + cash / nav) - 1.0) > 1e-6:
        return {"status": "NAV_INCOMPLETE", "reason": "accounting identity broken"}
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
    log_event(con, "NAV_CALCULATED", versions["benchmark_version"], None, account_id,
              {"date": date, "nav": nav})
    con.commit()
    return {"status": "STALE_PRICE" if stale else "OK", "nav": nav}


def nav_series(con: sqlite3.Connection, account_id: str) -> list[dict]:
    return [dict(r) for r in con.execute(
        "SELECT * FROM nav_daily WHERE account_id = ? ORDER BY date", (account_id,)).fetchall()]
