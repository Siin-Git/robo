"""Period-consistent performance and self-financing ledger attribution.

For each asset: P&L = ending value - starting value - signed trade cash flow.
Dividing interval P&L by the period's opening NAV links contributions in wealth
units (equivalently daily contribution times prior cumulative wealth). This
preserves compounding and reconciles exactly to the NAV change. It is valid
for this simulator's closed, no-external-flow accounts.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
import math
import numpy as np
import pandas as pd

PERIODS = {"1M": 1, "3M": 3, "6M": 6, "1Y": 12, "ALL": 0}
CORE_GROUPS = {
    "us_equity": "equity", "developed_ex_us": "equity",
    "emerging_markets": "equity", "korea_equity": "equity",
    "us_treasury": "bonds", "korea_treasury": "bonds", "tips": "bonds",
    "gold": "alternatives", "global_reit": "alternatives", "cash": "cash",
}


def calculate_report(nav, benchmark, holdings, trades, period="ALL"):
    """Input records contain ISO dates, numeric ledger fields; never writes."""
    if period not in PERIODS:
        raise ValueError("Invalid period")
    ordered = sorted(nav, key=lambda r: r["date"])
    valid = [r for r in ordered if r.get("status", "OK") != "NAV_INCOMPLETE"
             and math.isfinite(r["nav"]) and r["nav"] > 0]
    end = valid[-1]["date"] if valid else None
    if end and PERIODS[period]:
        cutoff = (pd.Timestamp(end) - pd.DateOffset(months=PERIODS[period])).date().isoformat()
        valid = [r for r in valid if r["date"] >= cutoff]
    metrics = dict.fromkeys(["cumulative_return", "benchmark_return", "difference_pp",
                            "mdd", "volatility", "tracking_error", "information_ratio"])
    result = {"status": "INSUFFICIENT_HISTORY", "period": period,
              "start": valid[0]["date"] if valid else None, "end": end,
              "since": ordered[0]["date"] if ordered else None, "observations": len(valid),
              "latest_recorded_date": ordered[-1]["date"] if ordered else None,
              "latest_recorded_status": ordered[-1].get("status", "OK") if ordered else None,
              "benchmark_name": "시스템 기준 CORE", "metrics": metrics,
              "series": [], "assets": [], "attribution": [],
              "quality": {"unresolved_intervals": 0, "stale_observations": sum(r.get("status") == "STALE_PRICE" for r in valid),
                          "missing_nav_dates": 0, "benchmark_complete": False}}
    # A single observed valuation is a known amount and index anchor, not a
    # measured zero return. Keep performance series empty until a second date.
    result["valuation"] = ({"date": end, "nav_krw": valid[-1]["nav"],
                            "cash_krw": valid[-1].get("cash"),
                            "index100": valid[-1]["nav"] / valid[0]["nav"] * 100}
                           if valid else None)
    result["anchor"] = ({"date": valid[0]["date"], "nav_krw": valid[0]["nav"], "index100": 100}
                        if valid else None)
    if len(valid) < 2:
        return result
    start, end = valid[0]["date"], valid[-1]["date"]
    initial = valid[0]["nav"]
    bm = {r["date"]: r["nav"] for r in benchmark if r["nav"] > 0 and r.get("status", "OK") == "OK"}
    common_endpoints = start in bm and end in bm
    bm0 = bm.get(start)
    hs = defaultdict(dict)
    for h in holdings:
        hs[h["date"]][h["asset_id"]] = h
    tx = defaultdict(list)
    for t in trades:
        if start < t["date"] <= end:
            tx[t["date"]].append(t)
    totals = defaultdict(float)
    totals["costs"] = totals["unexplained"] = 0.0
    averages = defaultdict(float)
    active_ids = set()
    price_edges = defaultdict(dict)
    weights_days = 0
    high = initial
    returns, active_returns = [], []
    previous = None
    def snapshot_ok(row):
        # Cash is non-interest bearing in this ledger; no imaginary cash yield.
        value = sum(h["market_value"] for h in hs[row["date"]].values()) + row.get("cash", 0)
        return abs(value - row["nav"]) <= max(.01, abs(row["nav"]) * 1e-7)
    for row in valid:
        d = row["date"]
        high = max(high, row["nav"])
        for aid, h in hs[d].items():
            active_ids.add(aid)
            totals[aid] += 0
            if d in (start, end):
                price_edges[aid][d] = h["price"]
        if row.get("cash", 0) != 0:
            active_ids.add("cash")
            totals["cash"] += 0
        if previous:
            prev_date = previous["date"]
            period_tx = [t for td, ts in tx.items() if prev_date < td <= d for t in ts]
            flow = defaultdict(float)
            for t in period_tx:
                aid = t["asset_id"]
                active_ids.add(aid)
                flow[aid] += math.copysign(t["gross_value"], t["quantity"]) if t["quantity"] else 0
            cost = -sum(t["cost"] for t in period_tx)
            explained = 0.0
            days = (date.fromisoformat(d) - date.fromisoformat(prev_date)).days
            if snapshot_ok(previous) and snapshot_ok(row):
                for aid in set(hs[prev_date]) | set(hs[d]) | set(flow):
                    v0 = hs[prev_date].get(aid, {}).get("market_value", 0)
                    v1 = hs[d].get(aid, {}).get("market_value", 0)
                    pnl = v1 - v0 - flow[aid]
                    totals[aid] += pnl / initial
                    explained += pnl
                    averages[aid] += v0 / previous["nav"] * days
                averages["cash"] += previous.get("cash", 0) / previous["nav"] * days
                weights_days += days
            else:
                result["quality"]["unresolved_intervals"] += 1
            totals["costs"] += cost / initial
            # Never attribute unexplained movements or missing holdings to an asset.
            totals["unexplained"] += (row["nav"] - previous["nav"] - explained - cost) / initial
            returns.append(row["nav"] / previous["nav"] - 1)
            if prev_date in bm and d in bm:
                active_returns.append(returns[-1] - (bm[d] / bm[prev_date] - 1))
            if len(pd.bdate_range(prev_date, d)) > 2:
                result["quality"]["missing_nav_dates"] += 1
        total_return = row["nav"] / initial - 1
        result["series"].append({"date": d, "personal": total_return,
                                 "benchmark": bm[d] / bm0 - 1 if bm0 and d in bm else None,
                                 "drawdown": row["nav"] / high - 1})
        result["attribution"].append({"date": d, "values": dict(totals), "total": total_return})
        previous = row
    metrics["cumulative_return"] = valid[-1]["nav"] / initial - 1
    metrics["mdd"] = min(r["drawdown"] for r in result["series"])
    if common_endpoints:
        metrics["benchmark_return"] = bm[end] / bm[start] - 1
        metrics["difference_pp"] = metrics["cumulative_return"] - metrics["benchmark_return"]
    result["quality"]["benchmark_complete"] = all(r["date"] in bm for r in valid)
    enough = len(returns) >= 30 and not result["quality"]["missing_nav_dates"] and not result["quality"]["stale_observations"]
    if enough:
        metrics["volatility"] = float(np.std(returns, ddof=1) * np.sqrt(252))
        if len(active_returns) == len(returns):
            sd = float(np.std(active_returns, ddof=1))
            metrics["tracking_error"] = sd * np.sqrt(252)
            metrics["information_ratio"] = float(np.mean(active_returns) / sd * np.sqrt(252)) if sd > 1e-12 else None
    for aid in sorted(active_ids):
        prices = price_edges[aid]
        asset_return = prices[end] / prices[start] - 1 if prices.get(start, 0) > 0 and end in prices else None
        result["assets"].append({"asset_id": aid, "group": CORE_GROUPS.get(aid, "themes"),
                                 "contribution": totals[aid], "average_weight": averages[aid] / weights_days if weights_days and not result["quality"]["unresolved_intervals"] else None,
                                 "price_return": asset_return})
    for aid in ("costs", "unexplained"):
        result["assets"].append({"asset_id": aid, "group": aid, "contribution": totals[aid], "average_weight": None, "price_return": None})
    # Populate all keys at every point so stacked series never bridge gaps.
    for point in result["attribution"]:
        point["values"] = {r["asset_id"]: point["values"].get(r["asset_id"], 0) for r in result["assets"]}
    result["status"] = "OK" if enough else "SHORT_HISTORY"
    return result
