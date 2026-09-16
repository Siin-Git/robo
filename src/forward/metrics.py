"""Performance, attribution and ranking (all derived, replay-safe)."""
from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from ..risk.drawdown import max_drawdown

WEEKS, DAYS = 52, 252
MIN_HISTORY = 30


def nav_frame(con: sqlite3.Connection, account_id: str) -> pd.DataFrame:
    rows = con.execute("SELECT date, nav, daily_return FROM nav_daily WHERE account_id = ?"
                       " ORDER BY date", (account_id,)).fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([dict(r) for r in rows])
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()


def perf_metrics(nav: pd.DataFrame, min_history: int = MIN_HISTORY) -> dict:
    n = len(nav)
    if n < 5:
        return {"status": "INSUFFICIENT_HISTORY"}
    rets = nav["daily_return"].dropna().to_numpy(float)
    rets = rets[1:] if n > 1 else rets  # first row has no prior
    out: dict = {"status": "OK", "n_obs": int(n),
                 "cumulative_return": float(nav["nav"].iloc[-1] / nav["nav"].iloc[0] - 1.0)}
    years = n / DAYS
    out["cagr"] = float((nav["nav"].iloc[-1] / nav["nav"].iloc[0]) ** (1 / years) - 1.0)
    out["mdd"] = max_drawdown(pd.Series(np.concatenate([[0.0], rets])))
    if n < min_history:
        out.update({"status": "INSUFFICIENT_HISTORY",
                    "annualized_volatility": None, "sharpe": None})
        return out
    vol = float(np.std(rets, ddof=1) * np.sqrt(DAYS))
    out["annualized_volatility"] = vol
    out["sharpe"] = float(np.mean(rets) / np.std(rets, ddof=1) * np.sqrt(DAYS)) if vol > 0 else None
    return out


def tracking_ir(personal: pd.DataFrame, core: pd.DataFrame) -> dict:
    idx = personal.index.intersection(core.index)
    if len(idx) < 5:
        return {"tracking_error": None, "information_ratio": None, "status": "INSUFFICIENT_HISTORY"}
    pr = personal.loc[idx, "daily_return"].to_numpy(float)[1:]
    cr = core.loc[idx, "daily_return"].to_numpy(float)[1:]
    active = pr - cr
    te = float(np.std(active, ddof=1) * np.sqrt(DAYS)) if len(active) > 1 else 0.0
    ir = float(np.mean(active) / np.std(active, ddof=1) * np.sqrt(DAYS)) \
        if len(active) > 1 and np.std(active, ddof=1) > 0 else (0.0 if te == 0 else None)
    out = {"tracking_error": te, "information_ratio": ir, "status": "OK"}
    if len(idx) < MIN_HISTORY:
        out["status"] = "INSUFFICIENT_HISTORY"
    out["active_cumulative"] = float(
        (personal.loc[idx, "nav"].iloc[-1] / personal.loc[idx, "nav"].iloc[0]) /
        (core.loc[idx, "nav"].iloc[-1] / core.loc[idx, "nav"].iloc[0]) - 1.0)
    return out


def attribution(con: sqlite3.Connection, account_id: str, core_account_id: str,
                start: str, end: str) -> dict:
    """Core Return + Active Theme Contribution + Costs + Residual (KRW)."""
    hold = pd.DataFrame([dict(r) for r in con.execute(
        "SELECT date, asset_id, market_value, weight FROM holdings_daily"
        " WHERE account_id = ? AND date BETWEEN ? AND ?",
        (account_id, start, end)).fetchall()])
    nav = nav_frame(con, account_id)
    total = float(nav.loc[end, "nav"] / nav.loc[start, "nav"] - 1.0) if len(nav) else 0.0
    if hold.empty:
        return {"total": total, "buckets": {}, "costs": 0.0, "residual": total}
    px = pd.DataFrame([dict(r) for r in con.execute(
        "SELECT asset_id, date, price FROM prices_daily")]).pivot(
        index="date", columns="asset_id", values="price").sort_index()
    px.index = pd.to_datetime(px.index)
    rets = px.pct_change()
    contrib: dict[str, float] = {}
    rdates = rets.index
    for (d, g) in hold.groupby(hold["date"]):
        d0 = pd.Timestamp(d)
        nxt = rdates[rdates > d0]
        if len(nxt) == 0:
            continue
        r1 = rets.loc[nxt[0]]
        for _, r in g.iterrows():
            a = r["asset_id"]
            c = float(r["weight"]) * float(r1[a]) if a in r1.index else 0.0
            key = ("theme:" + a.split(":", 1)[1]) if a.startswith("theme:") else "core"
            contrib[key] = contrib.get(key, 0.0) + (c if c == c else 0.0)
    costs = con.execute("SELECT COALESCE(SUM(transaction_cost),0) AS c FROM trades"
                        " WHERE account_id = ? AND execution_at BETWEEN ? AND ?",
                        (account_id, start, end)).fetchone()["c"]
    nav0 = float(nav.loc[start, "nav"])
    cost_drag = -float(costs) / nav0 if nav0 else 0.0
    explained = sum(contrib.values()) + cost_drag
    themes = {k: v for k, v in contrib.items() if k.startswith("theme:")}
    return {"total": total, "core": contrib.get("core", 0.0), "themes": themes,
            "costs": cost_drag, "residual": total - explained}


def rank_participants(rows: list[dict], key: str, common_only: bool = False) -> list[dict]:
    return sorted([r for r in rows if r.get(key) is not None],
                  key=lambda r: r[key], reverse=True)
