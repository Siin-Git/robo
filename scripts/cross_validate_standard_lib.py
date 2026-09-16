"""Cross-validation of the manual numpy stack vs standard libraries.

On a 64-bit environment with scikit-learn + scipy installed, compares:
  - manual Ledoit-Wolf vs sklearn LedoitWolf covariance
  - manual PGD max-Sharpe weights vs a direct scipy SLSQP solve

Without those libraries (e.g. current 32-bit env) it records
CROSS_VALIDATION: NOT RUN and exits 0 without failing the pipeline.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "outputs" / "latest" / "cross_validation.json"


def main() -> int:
    try:
        import sklearn  # noqa: F401
        from sklearn.covariance import LedoitWolf
        import scipy.optimize as so  # noqa: F401
    except Exception as exc:
        msg = f"CROSS_VALIDATION: NOT RUN (standard libs unavailable: {exc})"
        print(msg)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps({"status": "NOT RUN", "reason": str(exc)}, indent=2))
        return 0

    import numpy as np
    import pandas as pd

    from src.data.snapshot import load_snapshot
    from src.portfolio.constraints import ASSET_ORDER
    from src.portfolio.optimizer import max_sharpe, portfolio_stats
    from src.risk.covariance import _ledoit_wolf_manual

    snap = ROOT / "data" / "snapshots" / "SNAPSHOT_20260911_V0"
    if not (snap / "weekly_returns.csv").exists():
        print("CROSS_VALIDATION: NOT RUN (no snapshot found)")
        OUT.write_text(json.dumps({"status": "NOT RUN", "reason": "no snapshot"}, indent=2))
        return 0
    _, _, weekly_ret, _, _ = load_snapshot(snap)
    r5 = weekly_ret.iloc[-260:][ASSET_ORDER]
    X = r5.to_numpy(float)

    lw = LedoitWolf().fit(X).covariance_
    manual = _ledoit_wolf_manual(X)
    cov_diff = float(np.abs(np.asarray(lw) - manual).max())

    import yaml

    cfg = yaml.safe_load(open(ROOT / "config" / "optimizer_v0.yaml"))
    er = yaml.safe_load(open(ROOT / "config" / "expected_returns_v0.yaml"))
    mu = pd.Series({a: float(er["expected_returns_geometric"][a]["expected_return"]) for a in ASSET_ORDER})
    cov = pd.DataFrame(manual * 52.0, index=ASSET_ORDER, columns=ASSET_ORDER)
    w_manual = max_sharpe(mu, cov, 0.03, ASSET_ORDER, cfg["weight_bounds"],
                          cfg["group_constraints"], cfg["optimizer"], seed=42).to_numpy(float)

    m = mu.to_numpy(float)
    C = cov.to_numpy(float)
    lb = np.array([cfg["weight_bounds"][a]["min"] for a in ASSET_ORDER])
    ub = np.array([cfg["weight_bounds"][a]["max"] for a in ASSET_ORDER])
    idx = {a: i for i, a in enumerate(ASSET_ORDER)}
    cons = [{"type": "eq", "fun": lambda w: float(w.sum() - 1.0)}]
    for g in cfg["group_constraints"]:
        members = [idx[a] for a in g["assets"]]
        cons.append({"type": "ineq", "fun": lambda w, m=members, c=g["max"]: float(c - sum(w[i] for i in m))})

    def neg_sharpe(w):
        v = float(np.sqrt(max(w @ C @ w, 1e-18)))
        return float(-(w @ m - 0.03) / v)

    best, best_f = None, np.inf
    rng = np.random.default_rng(0)
    for _ in range(8):
        x0 = np.clip(rng.dirichlet(np.ones(len(ASSET_ORDER))), lb + 1e-9, ub - 1e-9)
        x0 = x0 / x0.sum()
        res = so.minimize(neg_sharpe, x0, bounds=list(zip(lb, ub)), constraints=cons, method="SLSQP")
        if res.success and res.fun < best_f:
            best, best_f = res.x, res.fun
    w_scipy = best / best.sum()
    w_diff = float(np.abs(w_manual - w_scipy).max())
    r1, v1, _ = portfolio_stats(w_manual, m, C, 0.03)
    r2, v2, _ = portfolio_stats(w_scipy, m, C, 0.03)
    report = {
        "status": "RUN",
        "cov_max_abs_diff": cov_diff,
        "weight_max_abs_diff": w_diff,
        "return_diff": abs(r1 - r2),
        "vol_diff": abs(v1 - v2),
    }
    print("CROSS_VALIDATION: RUN")
    print(json.dumps(report, indent=2))
    OUT.write_text(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
