"""Optimizer tests on synthetic risk model (no network)."""
import numpy as np
import pandas as pd
import pytest
import yaml
from pathlib import Path

from src.portfolio.constraints import ASSET_ORDER, validate_weights
from src.portfolio.optimizer import max_sharpe, min_variance, portfolio_stats

ROOT = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load(open(ROOT / "config" / "optimizer_v0.yaml"))
BOUNDS, GROUPS, OPT = CFG["weight_bounds"], CFG["group_constraints"], CFG["optimizer"]


def _synth_model(seed=3):
    rng = np.random.default_rng(seed)
    A = rng.normal(0, 0.02, size=(9, 9))
    C = pd.DataFrame(A @ A.T / 52 + np.eye(9) * 1e-4,
                     index=ASSET_ORDER, columns=ASSET_ORDER)
    mu = pd.Series(rng.uniform(0.03, 0.08, size=9), index=ASSET_ORDER)
    return mu, C


def test_min_variance_feasible():
    mu, C = _synth_model()
    w = min_variance(C, ASSET_ORDER, BOUNDS, GROUPS, OPT, seed=1)
    assert validate_weights(w.to_numpy(), ASSET_ORDER, BOUNDS, GROUPS) == []
    assert abs(w.sum() - 1.0) < 1e-6


def test_max_sharpe_feasible_and_finite():
    mu, C = _synth_model()
    w = max_sharpe(mu, C, 0.03, ASSET_ORDER, BOUNDS, GROUPS, OPT, seed=1)
    assert validate_weights(w.to_numpy(), ASSET_ORDER, BOUNDS, GROUPS) == []
    _, vol, sh = portfolio_stats(w.to_numpy(), mu.to_numpy(), C.to_numpy(), 0.03)
    assert np.isfinite(sh) and vol > 0


def test_infeasible_bounds_raise():
    mu, C = _synth_model()
    bad = {a: {"min": 0.5, "max": 0.6} for a in ASSET_ORDER}  # sum(min) >> 1
    with pytest.raises(Exception):
        min_variance(C, ASSET_ORDER, bad, GROUPS, OPT, seed=1)
