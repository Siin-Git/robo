"""Constrained efficient frontier via target-return grid."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .constraints import validate_weights
from .optimizer import max_return_greedy, min_variance, min_variance_with_target, portfolio_stats


def build_frontier(
    mu: pd.Series,
    cov: pd.DataFrame,
    rf: float,
    order,
    bounds_cfg,
    groups,
    cfg: dict,
    seed: int = 42,
    extra_warm: list | None = None,
) -> pd.DataFrame:
    n_points = int(cfg.get("frontier_points", 60))
    m = mu.loc[order].to_numpy(float)
    C = cov.loc[order, order].to_numpy(float)

    w_min = min_variance(cov, order, bounds_cfg, groups, cfg, seed=seed)
    r_min = float(w_min.to_numpy(float) @ m)
    w_max = max_return_greedy(mu, order, bounds_cfg, groups, cfg, seed=seed)
    r_max = float(w_max.to_numpy(float) @ m)
    if not r_max > r_min + 1e-12:
        raise RuntimeError("Degenerate frontier: max return <= min variance return")

    targets = np.linspace(r_min, r_max, n_points)
    rows = []
    prev_w = [w_min.to_numpy(float), w_max.to_numpy(float)]
    if extra_warm:
        prev_w.extend([np.asarray(x, dtype=float) for x in extra_warm])
    for i, t in enumerate(targets):
        try:
            w = min_variance_with_target(mu, cov, float(t), order, bounds_cfg, groups, cfg,
                                         seed=seed + i, warm=prev_w, n_start=5,
                                         polish_kicks=20, max_iter=400)
        except Exception:
            continue
        wv = w.to_numpy(float)
        issues = validate_weights(wv, order, bounds_cfg, groups)
        if issues:
            continue
        ret, vol, sh = portfolio_stats(wv, m, C, rf)
        if not (np.isfinite(ret) and np.isfinite(vol) and np.isfinite(sh)):
            continue
        row = {"target": float(t), "expected_return": ret, "volatility": vol, "sharpe": sh}
        for a in order:
            row[f"w_{a}"] = float(w.loc[a])
        rows.append(row)
        prev_w = [w.to_numpy(float)] + prev_w[:2]
    if not rows:
        raise RuntimeError("Frontier construction produced no valid points")
    df = pd.DataFrame(rows).sort_values("expected_return").reset_index(drop=True)
    df = df.drop_duplicates(subset=["expected_return", "volatility"]).reset_index(drop=True)
    df = df.dropna().reset_index(drop=True)
    if len(df) < 50:
        raise RuntimeError(f"Frontier has only {len(df)} points (< 50 required)")
    return df
