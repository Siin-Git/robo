"""Efficient Frontier service: reuses existing optimizer/frontier engine, no frontend math."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[3]

FRONTIER_VERSION = "CORE_FRONTIER_V0.3"

# Cache in-process (frontier is static until model changes)
_CACHE: dict | None = None


def _load_cfg():
    with open(ROOT / "config" / "optimizer_v0.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_bl_bundle():
    # Use BL posterior as mu for frontier (consistent with CORE_V0.3 base)
    import sys
    sys.path.insert(0, str(ROOT))
    from src.expected_return.strategic_v0 import build_optimizer_mu
    from src.expected_return.black_litterman import bl_full_pass
    from src.portfolio.reference import neutral_60_40_weights, reference_vol, extend_cov_with_cash
    from src.risk.covariance import annualize_covariance, ledoit_wolf_covariance, vols_from_cov
    from src.risk.returns import slice_lookback
    from src.data.snapshot import load_snapshot
    cfg = _load_cfg()
    er_cfg = yaml.safe_load(open(ROOT / "config" / "expected_returns_v0.yaml", encoding="utf-8"))
    # Covariance from frozen snapshot (5Y primary)
    snap = ROOT / "data" / "snapshots" / "SNAPSHOT_20260911_V0"
    _, _, weekly_ret, _, _ = load_snapshot(snap)
    r5 = slice_lookback(weekly_ret, 5)
    cov_w5 = ledoit_wolf_covariance(r5)
    cov5 = annualize_covariance(cov_w5, 52)
    # BL posterior
    from src.portfolio.constraints import ASSET_ORDER
    mu_cma9 = build_optimizer_mu(er_cfg, list(ASSET_ORDER))
    w_neutral = neutral_60_40_weights(cfg)
    from src.portfolio.reference import FULL_ORDER
    # Build cov10 for neutral vol but frontier uses 9-asset cov5
    # For BL, need neutral vol
    from src.portfolio.reference import reference_return
    import pandas as pd
    cov10_5 = extend_cov_with_cash(cov5)
    ref_vol5 = reference_vol(w_neutral, cov10_5)
    ref_ret = reference_return(w_neutral, __import__("src.portfolio.reference", fromlist=["extend_mu_with_cash"]).extend_mu_with_cash(mu_cma9, 0.03))
    blp = bl_full_pass(cov5, list(ASSET_ORDER), w_neutral.loc[list(ASSET_ORDER)], mu_cma9, 0.03, ref_ret, ref_vol5, 0.05, 0.25)
    mu_bl9 = blp["posterior_abs"]
    return mu_bl9, cov5, cfg


def get_frontier(force: bool = False) -> dict:
    global _CACHE
    if _CACHE is not None and not force:
        return _CACHE
    # Try file cache first (fast path for API)
    cache_path = ROOT / "outputs" / "api" / "frontier.json"
    if cache_path.exists() and not force:
        try:
            _CACHE = json.loads(cache_path.read_text(encoding="utf-8"))
            return _CACHE
        except Exception:
            pass
    mu_bl9, cov5, cfg = _load_bl_bundle()
    # Fast random-sampling frontier (UI needs discrete points, not exact optimizer frontier)
    # Generate many feasible portfolios, then filter to efficient frontier.
    from src.portfolio.constraints import ASSET_ORDER, get_bounds, validate_weights
    from src.portfolio.optimizer import portfolio_stats
    from src.portfolio.constraints import project_box_simplex, random_feasible
    import numpy as np
    import pandas as pd
    order = list(ASSET_ORDER)
    m = mu_bl9.loc[order].to_numpy(float)
    C = cov5.loc[order, order].to_numpy(float)
    lb, ub = get_bounds(order, cfg["weight_bounds"])
    groups = cfg["group_constraints"]
    rng = np.random.default_rng(42)
    candidates = []
    # Seed with min-var and max-return anchors (computed quickly)
    from src.portfolio.optimizer import min_variance, max_return_greedy
    try:
        w_min = min_variance(cov5, order, cfg["weight_bounds"], groups, cfg["optimizer"], seed=42).to_numpy(float)
        w_max = max_return_greedy(mu_bl9, order, cfg["weight_bounds"], groups, cfg["optimizer"], seed=42).to_numpy(float)
        candidates.extend([w_min, w_max])
    except Exception:
        pass
    # Also seed with frozen CORE weights
    try:
        frozen_w = json.loads((ROOT / "outputs" / "frozen" / "CORE_V0.3" / "weights.json").read_text(encoding="utf-8"))
        w_core = np.array([float(frozen_w.get(a, 0)) for a in order])
        if abs(w_core.sum() - 1.0) < 1e-9:
            candidates.append(w_core)
    except Exception:
        pass
    # Random feasible sampling
    for _ in range(15000):
        w = random_feasible(rng, lb, ub)
        # quick group check (reject if violated)
        ok = True
        idx = {a: i for i, a in enumerate(order)}
        for g in groups:
            tot = sum(float(w[idx[a]]) for a in g["assets"])
            if tot > float(g["max"]) + 1e-9:
                ok = False
                break
        if not ok:
            continue
        candidates.append(w)
    # Compute ret/vol for each
    pts = []
    for w in candidates:
        ret, vol, sh = portfolio_stats(w, m, C, 0.03)
        if not (np.isfinite(ret) and np.isfinite(vol)):
            continue
        pts.append((vol, ret, sh, w))
    # Efficient frontier: sort by vol, keep max ret so far
    pts.sort(key=lambda x: (x[0], -x[1]))
    efficient = []
    max_ret = -1e9
    for vol, ret, sh, w in pts:
        if ret > max_ret + 1e-9:
            efficient.append((vol, ret, sh, w))
            max_ret = ret
    # Sample 50 points evenly along efficient frontier
    if len(efficient) < 40:
        raise RuntimeError(f"Random frontier too sparse: {len(efficient)}")
    # Uniformly sample by index
    import numpy as _np
    idxs = _np.linspace(0, len(efficient) - 1, 50).astype(int)
    # Deduplicate
    idxs = sorted(set(int(i) for i in idxs))
    # Ensure at least 40
    if len(idxs) < 40:
        idxs = list(range(min(len(efficient), 50)))
    sampled = [efficient[i] for i in idxs]
    # Build points
    sampled.sort(key=lambda x: x[1])  # sort by return
    points = []
    for i, (vol, ret, sh, w) in enumerate(sampled):
        fid = f"F{i+1:03d}"
        weights = [{"asset_id": a, "weight": float(w[j])} for j, a in enumerate(order)]
        points.append({
            "frontier_id": fid,
            "index": int(i),
            "expected_return": float(ret),
            "volatility": float(vol),
            "sharpe": float(sh),
            "weights": weights,
        })
    # Benchmark marker: CORE_V0.3 closest by L1
    frozen_w = json.loads((ROOT / "outputs" / "frozen" / "CORE_V0.3" / "weights.json").read_text(encoding="utf-8"))
    # Filter to 9-asset part (ignore cash)
    frozen_9 = {k: float(v) for k, v in frozen_w.items() if k != "cash"}
    def l1(point):
        return sum(abs(next((w["weight"] for w in point["weights"] if w["asset_id"] == k), 0) - v) for k, v in frozen_9.items())
    bench = min(points, key=l1)
    # Min variance: lowest volatility
    min_var = min(points, key=lambda p: p["volatility"])
    # Tangency: max sharpe
    tangency = max(points, key=lambda p: p["sharpe"])
    # Asset points
    from src.risk.covariance import vols_from_cov
    vols = vols_from_cov(cov5)
    asset_info = {
        "us_equity": "미국주식", "developed_ex_us": "선진국 ex-US", "emerging_markets": "신흥국",
        "korea_equity": "한국주식", "us_treasury": "미국국채", "korea_treasury": "한국국채",
        "tips": "TIPS", "gold": "금", "global_reit": "글로벌 REIT",
    }
    assets = []
    for aid in ASSET_ORDER:
        assets.append({
            "asset_id": aid,
            "display_name": asset_info.get(aid, aid),
            "expected_return": float(mu_bl9.loc[aid]),
            "volatility": float(vols.loc[aid]),
        })
    vols_list = [p["volatility"] for p in points]
    result = {
        "frontier_version": FRONTIER_VERSION,
        "model_version": cfg.get("model_version", "CORE_V0.3"),
        "risk_model_version": "RISK_5Y_LW_FROZEN_V0",
        "expected_return_model": cfg.get("expected_return_model", "black_litterman_v0"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "min_volatility": float(min(vols_list)),
        "max_volatility": float(max(vols_list)),
        "benchmark_frontier_id": bench["frontier_id"],
        "min_variance_frontier_id": min_var["frontier_id"],
        "tangency_frontier_id": tangency["frontier_id"],
        "points": points,
        "assets": assets,
    }
    # Persist cache for fast API startup
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    except Exception:
        pass
    _CACHE = result
    return result


def find_point(frontier_id: str) -> dict | None:
    data = get_frontier()
    for p in data["points"]:
        if p["frontier_id"] == frontier_id:
            return p
    return None


def _nearest_point(volatility: float, points: list[dict]) -> dict:
    return min(points, key=lambda p: abs(float(p["volatility"]) - volatility))


def _frontier_return_at_vol(volatility: float, points: list[dict]) -> float | None:
    ordered = sorted(points, key=lambda p: float(p["volatility"]))
    if not ordered:
        return None
    if volatility <= float(ordered[0]["volatility"]):
        return float(ordered[0]["expected_return"])
    if volatility >= float(ordered[-1]["volatility"]):
        return float(ordered[-1]["expected_return"])
    for lo, hi in zip(ordered, ordered[1:]):
        lo_vol, hi_vol = float(lo["volatility"]), float(hi["volatility"])
        if lo_vol <= volatility <= hi_vol:
            if abs(hi_vol - lo_vol) < 1e-12:
                return float(hi["expected_return"])
            t = (volatility - lo_vol) / (hi_vol - lo_vol)
            return float(lo["expected_return"]) + t * (
                float(hi["expected_return"]) - float(lo["expected_return"])
            )
    return None


def describe_position(
    *,
    frontier_id: str | None = None,
    volatility: float | None = None,
    expected_return: float | None = None,
    label: str,
) -> dict:
    """Describe a portfolio in the CORE frontier coordinate system."""
    data = get_frontier()
    points = data["points"]
    point = find_point(frontier_id) if frontier_id else None
    if point is not None:
        vol = float(volatility if volatility is not None else point["volatility"])
        er = float(expected_return if expected_return is not None else point["expected_return"])
        nearest = point
        on_frontier = abs(vol - float(point["volatility"])) < 1e-9 and abs(
            er - float(point["expected_return"])
        ) < 1e-9
    elif volatility is not None:
        vol = float(volatility)
        er = float(expected_return) if expected_return is not None else None
        nearest = _nearest_point(vol, points)
        on_frontier = False
    else:
        return {
            "label": label,
            "frontier_id": frontier_id,
            "expected_return": expected_return,
            "volatility": None,
            "on_frontier": False,
            "nearest_frontier_id": None,
            "nearest_expected_return": None,
            "nearest_volatility": None,
            "volatility_delta": None,
            "return_gap": None,
            "method": "unavailable",
        }

    frontier_er = _frontier_return_at_vol(vol, points)
    return {
        "label": label,
        "frontier_id": point["frontier_id"] if point else frontier_id,
        "expected_return": er,
        "volatility": vol,
        "on_frontier": on_frontier,
        "nearest_frontier_id": nearest["frontier_id"],
        "nearest_expected_return": float(nearest["expected_return"]),
        "nearest_volatility": float(nearest["volatility"]),
        "volatility_delta": vol - float(nearest["volatility"]),
        "return_gap": (er - frontier_er) if er is not None and frontier_er is not None else None,
        "method": "exact_frontier_point" if on_frontier else "nearest_frontier_by_volatility",
    }
