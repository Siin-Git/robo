"""Phase 1.6 (V0.3 BL) tests. No network."""
import numpy as np
import pandas as pd
import yaml
from pathlib import Path

from src.expected_return.black_litterman import (
    black_litterman_posterior,
    build_cma_views,
    build_view_uncertainty,
    compute_delta,
    implied_equilibrium_returns,
)
from src.portfolio.bl_benchmark import build_bl_portfolio
from src.portfolio.constraints import ASSET_ORDER, validate_weights
from src.portfolio.optimizer import portfolio_stats
from src.portfolio.reference import FULL_ORDER, neutral_60_40_weights, reference_vol
from src.portfolio.sensitivity import shock_mu

ROOT = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load(open(ROOT / "config" / "optimizer_v0.yaml", encoding="utf-8"))
ER_CFG = yaml.safe_load(open(ROOT / "config" / "expected_returns_v0.yaml", encoding="utf-8"))
BOUNDS, GROUPS, OPT = CFG["weight_bounds"], CFG["group_constraints"], CFG["optimizer"]
RF, TAU = 0.03, 0.05
MU = pd.Series({a: float(ER_CFG["expected_returns_geometric"][a]["expected_return"])
                for a in ASSET_ORDER})


def _synth_cov9(seed=21):
    rng = np.random.default_rng(seed)
    A = rng.normal(0, 0.02, size=(9, 9))
    return pd.DataFrame(A @ A.T / 52 + np.eye(9) * 1e-4,
                        index=list(ASSET_ORDER), columns=list(ASSET_ORDER))


def test_delta_formula():
    assert abs(compute_delta(0.05736, 0.08924, 0.03) - (0.02736 / 0.08924**2)) < 1e-9


def test_prior_formula_tiny_case():
    C = pd.DataFrame([[0.04, 0.01], [0.01, 0.09]], index=["a", "b"], columns=["a", "b"])
    w = pd.Series([0.5, 0.3], index=["a", "b"])
    pi = implied_equilibrium_returns(C, w, 2.0)
    np.testing.assert_allclose(pi.to_numpy(), 2.0 * (C.to_numpy() @ w.to_numpy()), rtol=1e-12)


def test_bl_no_view_returns_prior():
    C = _synth_cov9()
    w = pd.Series(np.full(9, 0.1), index=list(ASSET_ORDER))
    pi = implied_equilibrium_returns(C, w, 3.0)
    P, Q = build_cma_views(MU, RF, ASSET_ORDER)
    Om = build_view_uncertainty(C, P, TAU, 0.0)
    post = black_litterman_posterior(pi, C, P, Q, Om, TAU, 0.0)
    pd.testing.assert_series_equal(post, pi)


def test_bl_full_confidence_returns_views():
    C = _synth_cov9()
    w = pd.Series(np.full(9, 0.1), index=list(ASSET_ORDER))
    pi = implied_equilibrium_returns(C, w, 3.0)
    P, Q = build_cma_views(MU, RF, ASSET_ORDER)
    Om = build_view_uncertainty(C, P, TAU, 1.0)
    post = black_litterman_posterior(pi, C, P, Q, Om, TAU, 1.0)
    np.testing.assert_allclose(post.to_numpy(), Q, rtol=1e-9, atol=1e-12)


def test_bl_direction_monotone_in_confidence():
    C = _synth_cov9()
    w = pd.Series(np.full(9, 0.1), index=list(ASSET_ORDER))
    pi = implied_equilibrium_returns(C, w, 3.0)
    P, Q = build_cma_views(MU, RF, ASSET_ORDER)
    prev = None
    for c in (0.10, 0.25, 0.50, 0.75):
        Om = build_view_uncertainty(C, P, TAU, c)
        post = black_litterman_posterior(pi, C, P, Q, Om, TAU, c).to_numpy()
        gap = np.abs(Q - post)
        if prev is not None:
            assert (gap <= prev + 1e-12).all(), "posterior must move toward views with confidence"
        prev = gap


def test_bl_shapes_and_finite():
    C = _synth_cov9()
    P, Q = build_cma_views(MU, RF, ASSET_ORDER)
    assert P.shape == (9, 9) and Q.shape == (9,)
    Om = build_view_uncertainty(C, P, TAU, 0.25)
    assert Om.shape == (9, 9)
    assert np.allclose(Om, np.diag(np.diag(Om)))
    w = pd.Series(np.full(9, 0.1), index=list(ASSET_ORDER))
    pi = implied_equilibrium_returns(C, w, 3.0)
    post = black_litterman_posterior(pi, C, P, Q, Om, TAU, 0.25)
    assert np.isfinite(post.to_numpy()).all()


def test_v03_risk_anchor_and_constraints():
    from src.portfolio.reference import extend_cov_with_cash
    C9 = _synth_cov9()
    w_neu = neutral_60_40_weights(CFG)
    res = build_bl_portfolio(MU, C9, w_neu, RF, TAU, 0.25, BOUNDS, GROUPS, OPT, seed=5)
    w = res["weights"]
    assert validate_weights(w.to_numpy(), FULL_ORDER, BOUNDS, GROUPS) == []
    assert res["vol"] <= res["target_vol"] + 5e-4


def test_v03_determinism():
    C9 = _synth_cov9()
    w_neu = neutral_60_40_weights(CFG)
    kw = dict(mu_cma9=MU, cov9=C9, w_neutral10=w_neu, rf=RF, tau=TAU, confidence=0.25,
              bounds_cfg=BOUNDS, groups=GROUPS, opt_cfg=OPT, seed=5)
    pd.testing.assert_series_equal(build_bl_portfolio(**kw)["weights"],
                                   build_bl_portfolio(**kw)["weights"])


def test_shock_flows_through_bl_to_optimizer():
    C9 = _synth_cov9()
    w_neu = neutral_60_40_weights(CFG)
    kw = dict(cov9=C9, w_neutral10=w_neu, rf=RF, tau=TAU, confidence=0.25,
              bounds_cfg=BOUNDS, groups=GROUPS, opt_cfg=OPT, seed=5)
    base = build_bl_portfolio(mu_cma9=MU, **kw)
    sh = build_bl_portfolio(mu_cma9=shock_mu(MU, "us_equity", 0.005), **kw)
    # Posterior must reflect the shocked view...
    assert abs(sh["posterior_abs"].loc["us_equity"] - base["posterior_abs"].loc["us_equity"]) > 1e-6
    # ...and stay feasible / finite.
    assert validate_weights(sh["weights"].to_numpy(), FULL_ORDER, BOUNDS, GROUPS) == []
    assert np.isfinite(sh["ret"]) and np.isfinite(sh["vol"])
