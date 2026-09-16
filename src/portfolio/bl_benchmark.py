"""V0.3 builder: Neutral-implied BL posterior -> risk-anchored max-return."""
from __future__ import annotations

import pandas as pd

from ..expected_return.black_litterman import bl_full_pass
from .constraints import ASSET_ORDER
from .optimizer import max_return_with_vol_cap, portfolio_stats
from .reference import extend_cov_with_cash, extend_mu_with_cash, reference_return, reference_vol


def build_bl_portfolio(mu_cma9: pd.Series, cov9: pd.DataFrame, w_neutral10: pd.Series,
                       rf: float, tau: float, confidence: float,
                       bounds_cfg: dict, groups: list, opt_cfg: dict,
                       seed: int = 42) -> dict:
    """Full V0.3 pass: prior, views, posterior, anchored optimization."""
    order9 = list(ASSET_ORDER)
    w_risky = w_neutral10.loc[order9]
    cov10 = extend_cov_with_cash(cov9)
    mu_cma10 = extend_mu_with_cash(mu_cma9, rf)
    target_vol = reference_vol(w_neutral10, cov10)
    ref_ret = reference_return(w_neutral10, mu_cma10)
    blp = bl_full_pass(cov9.loc[order9, order9], order9, w_risky, mu_cma9, rf,
                       ref_ret, target_vol, tau, confidence)
    mu_bl10 = extend_mu_with_cash(blp["posterior_abs"], rf)
    w = max_return_with_vol_cap(mu_bl10, cov10, target_vol, list(mu_bl10.index),
                                bounds_cfg, groups, opt_cfg, seed=seed)
    ret, vol, sh = portfolio_stats(w.to_numpy(float), mu_bl10.to_numpy(float),
                                   cov10.to_numpy(float), rf)
    return {"weights": w, "target_vol": target_vol, "ref_ret": ref_ret,
            "ret": ret, "vol": vol, "sharpe": sh, "mu_bl10": mu_bl10,
            "cov10": cov10, **blp}
