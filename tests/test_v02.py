"""Phase 1.5 (V0.2) tests: ER convention, hedged bonds, horizons, reference,
target-risk, sensitivity scenarios, snapshot reproducibility. No network.
"""
import numpy as np
import pandas as pd
import yaml
from pathlib import Path

from src.data.preprocessing import build_krw_weekly_returns
from src.data.snapshot import load_snapshot, save_snapshot
from src.expected_return.conversions import geometric_to_arithmetic
from src.expected_return.strategic_v0 import build_optimizer_mu
from src.portfolio.constraints import ASSET_ORDER, validate_weights
from src.portfolio.optimizer import max_return_with_vol_cap, portfolio_stats
from src.portfolio.reference import (
    FULL_ORDER,
    extend_cov_with_cash,
    extend_mu_with_cash,
    neutral_60_40_weights,
    reference_vol,
)
from src.portfolio.sensitivity import shock_mu
from src.risk.covariance import annualize_covariance, ledoit_wolf_covariance
from src.risk.returns import slice_lookback

ROOT = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load(open(ROOT / "config" / "optimizer_v0.yaml"))
ER_CFG = yaml.safe_load(open(ROOT / "config" / "expected_returns_v0.yaml"))
BOUNDS, GROUPS, OPT = CFG["weight_bounds"], CFG["group_constraints"], CFG["optimizer"]
RF = 0.03


def _synth_weekly(n=300, seed=11):
    rng = np.random.default_rng(seed)
    cols = list(ASSET_ORDER)
    return pd.DataFrame(rng.normal(0.001, 0.02, size=(n, len(cols))),
                        index=pd.date_range("2020-01-03", periods=n, freq="W-FRI"),
                        columns=cols)


def test_optimizer_uses_strategic_er_not_arith_conversion():
    mu = build_optimizer_mu(ER_CFG, ASSET_ORDER)
    for a in ASSET_ORDER:
        assert abs(mu.loc[a] - ER_CFG["expected_returns_geometric"][a]["expected_return"]) < 1e-12
    # Korea case from Phase 1 finding: conversion would give ~10.8%, optimizer must use 6.8%.
    assert abs(mu.loc["korea_equity"] - 0.068) < 1e-12
    assert geometric_to_arithmetic(0.068, 0.2837) > 0.10  # conversion exists but unused


def test_hedged_bond_excludes_fx():
    idx = pd.bdate_range("2024-01-01", periods=40)
    rng = np.random.default_rng(2)
    usd = pd.Series(100 * np.cumprod(1 + rng.normal(0, 0.005, 40)), index=idx)
    fx = pd.Series(1300 * np.cumprod(1 + rng.normal(0, 0.004, 40)), index=idx)
    cfg = {"assets": [
        {"asset_id": "bond_h", "currency": "USD", "fx_treatment": "hedged"},
        {"asset_id": "eq_u", "currency": "USD", "fx_treatment": "unhedged"},
    ]}
    ret, _, _ = build_krw_weekly_returns({"bond_h": usd, "eq_u": usd}, fx, cfg)
    local = usd.resample("W-FRI").last().pct_change().dropna()
    pd.testing.assert_series_equal(ret["bond_h"].dropna(), local.loc[ret.index].rename("bond_h"),
                                   check_names=False)
    # unhedged leg must differ whenever FX moves
    assert not np.allclose(ret["eq_u"].dropna().to_numpy(),
                           local.loc[ret.index].to_numpy())


def test_risk_horizons_independent():
    r = _synth_weekly()
    r5 = slice_lookback(r, 5)
    r3 = slice_lookback(r, 3)
    assert len(r5) == 260 and len(r3) == 156
    c5 = annualize_covariance(ledoit_wolf_covariance(r5))
    c3 = annualize_covariance(ledoit_wolf_covariance(r3))
    assert c5.shape == c3.shape == (9, 9)
    assert not np.allclose(c5.to_numpy(), c3.to_numpy())


def test_neutral_reference_weights():
    w = neutral_60_40_weights(CFG)
    assert abs(w.sum() - 1.0) < 1e-12
    assert abs(w.loc[ASSET_ORDER[:4]].sum() - 0.60) < 1e-12
    assert abs(w.drop(ASSET_ORDER[:4]).sum() - 0.40) < 1e-12
    assert abs(w.loc["cash"] - 0.05) < 1e-12


def _synth_problem10(seed=7):
    rng = np.random.default_rng(seed)
    A = rng.normal(0, 0.02, size=(9, 9))
    C9 = pd.DataFrame(A @ A.T / 52 + np.eye(9) * 1e-4, index=ASSET_ORDER, columns=ASSET_ORDER)
    mu9 = build_optimizer_mu(ER_CFG, ASSET_ORDER)
    return extend_mu_with_cash(mu9, RF), extend_cov_with_cash(C9)


def test_target_risk_cap_respected():
    mu10, cov10 = _synth_problem10()
    w_ref = neutral_60_40_weights(CFG)
    tgt = reference_vol(w_ref, cov10)
    w = max_return_with_vol_cap(mu10, cov10, tgt, FULL_ORDER, BOUNDS, GROUPS, OPT, seed=3)
    assert validate_weights(w.to_numpy(), FULL_ORDER, BOUNDS, GROUPS) == []
    _, vol, _ = portfolio_stats(w.to_numpy(), mu10.to_numpy(), cov10.to_numpy(), RF)
    assert vol <= tgt + 5e-4


def test_er_shock_scenarios_build():
    mu9 = build_optimizer_mu(ER_CFG, ASSET_ORDER)
    mu10, cov10 = _synth_problem10()
    tgt = reference_vol(neutral_60_40_weights(CFG), cov10)
    w0 = max_return_with_vol_cap(mu10, cov10, tgt, FULL_ORDER, BOUNDS, GROUPS, OPT, seed=3)
    mu_s = extend_mu_with_cash(shock_mu(mu9, "us_equity", 0.005), RF)
    w_s = max_return_with_vol_cap(mu_s, cov10, tgt, FULL_ORDER, BOUNDS, GROUPS, OPT, seed=3)
    assert validate_weights(w_s.to_numpy(), FULL_ORDER, BOUNDS, GROUPS) == []
    r0, _, _ = portfolio_stats(w0.to_numpy(), mu10.to_numpy(), cov10.to_numpy(), RF)
    r1, _, _ = portfolio_stats(w_s.to_numpy(), mu_s.to_numpy(), cov10.to_numpy(), RF)
    assert np.isfinite(r0) and np.isfinite(r1)


def test_snapshot_reproducibility(tmp_path):
    idx = pd.bdate_range("2023-01-02", periods=120)
    rng = np.random.default_rng(4)
    prices, cols = {}, list(ASSET_ORDER)
    for c in cols:
        prices[c] = pd.Series(100 * np.cumprod(1 + rng.normal(0.001, 0.01, 120)), index=idx)
    fx = pd.Series(1300 * np.cumprod(1 + rng.normal(0, 0.002, 120)), index=idx)
    cfg = {"assets": [{"asset_id": c, "currency": "USD", "fx_treatment": "unhedged"} for c in cols]}
    ret, pxw, _ = build_krw_weekly_returns(prices, fx, cfg)
    snap = tmp_path / "snap"
    save_snapshot(snap, prices, fx, ret, pxw, {"tickers": {c: c for c in cols}})
    # Snapshot mode re-runs preprocessing from raw daily (bitwise-exact CSV
    # round-trip), so the rebuild must match the live frame exactly.
    prices2, fx2, stored, _, _ = load_snapshot(snap)
    ret2, _, _ = build_krw_weekly_returns(prices2, fx2, cfg)
    # Bitwise-exact: hex float storage + identical code path.
    pd.testing.assert_frame_equal(ret, ret2, check_freq=False, check_exact=True)

    mu10, _ = _synth_problem10()
    cov10 = extend_cov_with_cash(annualize_covariance(ledoit_wolf_covariance(ret)))
    tgt = reference_vol(neutral_60_40_weights(CFG), cov10)
    w1 = max_return_with_vol_cap(mu10, cov10, tgt, FULL_ORDER, BOUNDS, GROUPS, OPT, seed=9)
    cov10b = extend_cov_with_cash(annualize_covariance(ledoit_wolf_covariance(ret2)))
    w2 = max_return_with_vol_cap(mu10, cov10b, tgt, FULL_ORDER, BOUNDS, GROUPS, OPT, seed=9)
    pd.testing.assert_series_equal(w1, w2)
