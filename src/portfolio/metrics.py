"""Portfolio metrics + diagnostic (non-predictive) sanity check."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..risk.drawdown import max_drawdown

WEEKS = 52


def portfolio_return_series(weekly_returns: pd.DataFrame, weights: pd.Series) -> pd.Series:
    w = weights.loc[weekly_returns.columns].to_numpy(float)
    return pd.Series(weekly_returns.to_numpy(float) @ w, index=weekly_returns.index)


def summarize_series(r: pd.Series, rf: float = 0.0) -> dict:
    r = r.dropna()
    n = len(r)
    if n < 2:
        raise ValueError("Not enough observations for metrics")
    wealth = float(np.prod(1.0 + r.to_numpy(float)))
    years = n / WEEKS
    cagr = float(wealth ** (1.0 / years) - 1.0) if wealth > 0 else float("nan")
    vol = float(r.std(ddof=1) * np.sqrt(WEEKS))
    excess = r - rf / WEEKS
    sharpe = float(excess.mean() / r.std(ddof=1) * np.sqrt(WEEKS)) if r.std(ddof=1) > 0 else float("nan")
    return {
        "cagr": cagr,
        "ann_vol": vol,
        "sharpe": sharpe,
        "mdd": max_drawdown(r),
        "ending_wealth": wealth,
        "n_weeks": int(n),
    }


def sanity_check(
    weekly_returns: pd.DataFrame, portfolios: dict[str, pd.Series], rf: float = 0.0
) -> pd.DataFrame:
    """Diagnostic comparison of static-weight portfolios on common history.

    NOTE: not a walk-forward backtest; current weights applied to history
    to inspect behavior characteristics only.
    """
    rows = []
    for name, w in portfolios.items():
        s = portfolio_return_series(weekly_returns, w)
        m = summarize_series(s, rf)
        m["portfolio"] = name
        rows.append(m)
    df = pd.DataFrame(rows).set_index("portfolio")
    return df[["cagr", "ann_vol", "sharpe", "mdd", "ending_wealth", "n_weeks"]]
