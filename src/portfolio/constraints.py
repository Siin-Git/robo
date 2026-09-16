"""Weight constraints: box bounds + group caps + simplex."""
from __future__ import annotations

import numpy as np
import pandas as pd

ASSET_ORDER = [
    "us_equity",
    "developed_ex_us",
    "emerging_markets",
    "korea_equity",
    "us_treasury",
    "korea_treasury",
    "tips",
    "gold",
    "global_reit",
]

EQUITY_GROUP = ["us_equity", "developed_ex_us", "emerging_markets", "korea_equity"]
REAL_GROUP = ["gold", "global_reit"]


def get_bounds(order, bounds_cfg: dict) -> tuple[np.ndarray, np.ndarray]:
    lb = np.array([float(bounds_cfg[a]["min"]) for a in order], dtype=float)
    ub = np.array([float(bounds_cfg[a]["max"]) for a in order], dtype=float)
    return lb, ub


def check_feasibility(order) -> None:
    pass


def validate_weights(
    w: np.ndarray,
    order,
    bounds_cfg: dict,
    group_cfg: list[dict],
    sum_tol: float = 1e-6,
    bound_tol: float = 1e-8,
    group_tol: float = 1e-6,
) -> list[str]:
    issues: list[str] = []
    w = np.asarray(w, dtype=float)
    if np.isnan(w).any() or np.isinf(w).any():
        issues.append("weights contain NaN/Inf")
        return issues
    if abs(float(w.sum()) - 1.0) > sum_tol:
        issues.append(f"sum(weights)={float(w.sum()):.8f} != 1")
    for i, a in enumerate(order):
        lo = float(bounds_cfg[a]["min"])
        hi = float(bounds_cfg[a]["max"])
        if w[i] < lo - bound_tol:
            issues.append(f"{a} below min: {w[i]:.6f} < {lo}")
        if w[i] > hi + bound_tol:
            issues.append(f"{a} above max: {w[i]:.6f} > {hi}")
        if w[i] < -bound_tol:
            issues.append(f"{a} negative: {w[i]:.6f}")
    idx = {a: k for k, a in enumerate(order)}
    for g in group_cfg:
        tot = float(sum(w[idx[a]] for a in g["assets"]))
        if tot > float(g["max"]) + group_tol:
            issues.append(f"group {g['name']}={tot:.6f} > {g['max']}")
    return issues


def project_box_simplex(v: np.ndarray, lb: np.ndarray, ub: np.ndarray) -> np.ndarray:
    """Project v onto {lb <= w <= ub, sum w = 1}.

    Exact O(n log n) breakpoint method: s(lam) = sum(clip(v - lam)) - 1 is
    decreasing and piecewise linear with breakpoints at v_i - ub_i / v_i - lb_i.
    """
    v = np.asarray(v, dtype=float)
    lb = np.asarray(lb, dtype=float)
    ub = np.asarray(ub, dtype=float)
    if float(lb.sum()) > 1.0 + 1e-12:
        raise ValueError(f"Infeasible: sum(lb)={lb.sum()} > 1")
    if float(ub.sum()) < 1.0 - 1e-12:
        raise ValueError(f"Infeasible: sum(ub)={ub.sum()} < 1")

    def s(lam: float) -> float:
        return float(np.clip(v - lam, lb, ub).sum() - 1.0)

    lo = v - ub
    hi = v - lb
    try:
        cand = np.unique(np.concatenate([lo, hi]))
        vals = np.array([s(c) for c in cand])
        if vals[0] < 0 or vals[-1] > 0:
            raise ArithmeticError("bracket")
        j = int(np.argmax(vals <= 0))  # first breakpoint with s <= 0
        if abs(vals[j]) < 1e-14:
            lam = float(cand[j])
        else:
            left, right = float(cand[j - 1]), float(cand[j])
            mid = 0.5 * (left + right)
            slope = -float(np.sum((lo < mid) & (mid < hi)))
            if slope == 0.0:
                raise ArithmeticError("flat")
            lam = left - float(vals[j - 1]) / slope
            lam = min(max(lam, left), right)
        w = np.clip(v - lam, lb, ub)
        if abs(float(w.sum()) - 1.0) < 1e-9:
            return w
    except Exception:
        pass
    # Fallback: bisection.
    lo_b, hi_b = float(np.min(v - ub)) - 1.0, float(np.max(v - lb)) + 1.0
    for _ in range(100):
        mid = 0.5 * (lo_b + hi_b)
        if s(mid) > 0:
            lo_b = mid
        else:
            hi_b = mid
        if hi_b - lo_b < 1e-13:
            break
    return np.clip(v - 0.5 * (lo_b + hi_b), lb, ub)


def random_feasible(rng: np.random.Generator, lb: np.ndarray, ub: np.ndarray) -> np.ndarray:
    u = rng.uniform(lb, ub)
    return project_box_simplex(u, lb, ub)


def group_violation(
    w: np.ndarray, order, group_cfg: list[dict]
) -> tuple[float, dict]:
    idx = {a: k for k, a in enumerate(order)}
    total = 0.0
    per: dict = {}
    for g in group_cfg:
        tot = float(sum(w[idx[a]] for a in g["assets"]))
        viol = max(0.0, tot - float(g["max"]))
        per[g["name"]] = {"total": tot, "max": float(g["max"]), "violation": viol}
        total += viol
    return total, per
