"""Sensitivity + bound diagnostics (V0.2, Section 11-13)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def weight_l1_diff(w1: pd.Series, w2: pd.Series) -> tuple[float, pd.Series]:
    a, b = w1.align(w2, join="inner")
    d = (a - b).abs()
    return float(d.sum()), d.sort_values(ascending=False)


def shock_mu(mu: pd.Series, asset: str, delta: float) -> pd.Series:
    out = mu.copy()
    out.loc[asset] = float(out.loc[asset]) + float(delta)
    return out


def summarize_bound_hits(w: pd.Series, bounds_cfg: dict, tol: float = 1e-6) -> pd.DataFrame:
    rows = []
    for a in w.index:
        lo = float(bounds_cfg[a]["min"])
        hi = float(bounds_cfg[a]["max"])
        v = float(w.loc[a])
        if abs(v - hi) <= tol:
            hit = "upper"
        elif abs(v - lo) <= tol:
            hit = "lower"
        else:
            hit = "none"
        rows.append({"asset": a, "weight": v, "min": lo, "max": hi, "bound_hit": hit})
    return pd.DataFrame(rows)


def zero_weight_report(w_risky: pd.Series, tol: float = 1e-9) -> dict:
    zeros = [a for a in w_risky.index if abs(float(w_risky.loc[a])) <= tol]
    n = len(zeros)
    if n >= 5:
        level = "strong warning"
    elif n >= 3:
        level = "warning"
    else:
        level = "ok"
    return {"n_zero": n, "zero_assets": zeros, "level": level}
