"""Frontier tests on synthetic risk model (no network)."""
import numpy as np
import pandas as pd
import yaml
from pathlib import Path

from src.portfolio.constraints import ASSET_ORDER
from src.portfolio.frontier import build_frontier

ROOT = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load(open(ROOT / "config" / "optimizer_v0.yaml"))
BOUNDS, GROUPS, OPT = CFG["weight_bounds"], CFG["group_constraints"], CFG["optimizer"]


def _synth_model(seed=5):
    rng = np.random.default_rng(seed)
    A = rng.normal(0, 0.02, size=(9, 9))
    C = pd.DataFrame(A @ A.T / 52 + np.eye(9) * 1e-4,
                     index=ASSET_ORDER, columns=ASSET_ORDER)
    mu = pd.Series(rng.uniform(0.03, 0.08, size=9), index=ASSET_ORDER)
    return mu, C


def test_frontier_valid():
    mu, C = _synth_model()
    cfg = dict(OPT, frontier_points=55)
    df = build_frontier(mu, C, 0.03, ASSET_ORDER, BOUNDS, GROUPS, cfg, seed=2)
    assert len(df) >= 50
    assert df[["expected_return", "volatility", "sharpe"]].notna().all().all()
    assert np.isfinite(df[["expected_return", "volatility", "sharpe"]].to_numpy()).all()
    wcols = [f"w_{a}" for a in ASSET_ORDER]
    sums = df[wcols].sum(axis=1)
    assert ((sums - 1.0).abs() < 1e-6).all()
    assert not df.duplicated(subset=["expected_return", "volatility"]).any()
