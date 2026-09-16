"""Run guardrails: PASS only when every check holds.

The constrained benchmark must satisfy all weight constraints. Comparators
(equal weight 1/9 per spec, 60/40) are reference portfolios: their
constraint notes are reported transparently but do not flip STATUS, since
e.g. 1/9 mechanically exceeds the 10% global_reit cap by design.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def run_checks(ctx: dict) -> tuple[bool, list[str], list[str]]:
    issues: list[str] = []
    notes: list[str] = []
    weekly: pd.DataFrame = ctx["weekly_returns"]
    cov: pd.DataFrame = ctx["annual_cov"]
    er: pd.DataFrame = ctx["er_table"]
    order = ctx["order"]

    if weekly.empty:
        issues.append("weekly returns empty (price data missing)")
    look = ctx.get("lookback_3y")
    if look is not None and len(look) > 0:
        miss = float(look.isna().mean().mean())
        if miss > float(ctx.get("max_missing_fraction_3y", 0.05)):
            issues.append(f"excessive missing in 3Y window: {miss:.3%}")
    if cov.isna().any().any() or np.isinf(cov.to_numpy(float)).any():
        issues.append("covariance contains NaN/Inf")
    for a in order:
        if a not in er.index or not np.isfinite(er.loc[a, "arith_er"]):
            issues.append(f"expected return missing/non-finite for {a}")
    wv = np.asarray(ctx["w_bench"], float)
    if abs(wv.sum() - 1.0) > 1e-4:
        issues.append(f"benchmark: sum(weights)={wv.sum():.6f}")
    for v in ctx.get("weight_issues", {}).get("benchmark", []):
        issues.append(f"benchmark: {v}")
    for name, w in list(ctx.get("comparators", {}).items()):
        if abs(float(np.asarray(w, float).sum()) - 1.0) > 1e-4:
            notes.append(f"{name}: sum(weights)={float(np.asarray(w, float).sum()):.6f}")
        for v in ctx.get("weight_issues", {}).get(name, []):
            notes.append(f"{name}: {v}")
    if not np.isfinite(ctx.get("bench_sharpe", np.nan)):
        issues.append("tangency Sharpe is NaN/Inf")
    if ctx.get("stale", False):
        issues.append(f"latest data too old: {ctx.get('data_end')}")
    if not ctx.get("optimizer_ok", False):
        issues.append("optimizer reported infeasible")
    return (len(issues) == 0), issues, notes
