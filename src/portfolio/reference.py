"""Neutral 60/40 risk-anchor reference + cash-aware helpers (V0.2)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .constraints import ASSET_ORDER

FULL_ORDER = list(ASSET_ORDER) + ["cash"]
CASH_ID = "cash"


def neutral_60_40_weights(cfg_opt: dict) -> pd.Series:
    spec = cfg_opt.get("neutral_60_40")
    if not spec:
        raise ValueError("neutral_60_40 block missing in optimizer config")
    w = pd.Series([float(spec[a]) for a in FULL_ORDER], index=FULL_ORDER)
    if abs(w.sum() - 1.0) > 1e-12:
        raise ValueError(f"neutral 60/40 weights sum to {w.sum()}")
    eq = w.loc[ASSET_ORDER[:4]].sum()
    if abs(eq - 0.60) > 1e-12:
        raise ValueError(f"neutral equity sleeve is {eq}, expected 0.60")
    return w


def extend_mu_with_cash(mu_risky: pd.Series, rf: float) -> pd.Series:
    mu = pd.Series({a: float(mu_risky.loc[a]) for a in ASSET_ORDER})
    mu[CASH_ID] = float(rf)
    return mu.loc[FULL_ORDER]


def extend_cov_with_cash(cov_risky: pd.DataFrame) -> pd.DataFrame:
    cov = pd.DataFrame(0.0, index=FULL_ORDER, columns=FULL_ORDER)
    cov.loc[ASSET_ORDER, ASSET_ORDER] = cov_risky.loc[ASSET_ORDER, ASSET_ORDER].to_numpy(float)
    return cov


def reference_vol(weights_full: pd.Series, cov_full: pd.DataFrame) -> float:
    w = weights_full.loc[FULL_ORDER].to_numpy(float)
    C = cov_full.loc[FULL_ORDER, FULL_ORDER].to_numpy(float)
    return float(np.sqrt(max(w @ C @ w, 0.0)))


def reference_return(weights_full: pd.Series, mu_full: pd.Series) -> float:
    return float(weights_full.loc[FULL_ORDER].to_numpy(float) @ mu_full.loc[FULL_ORDER].to_numpy(float))
