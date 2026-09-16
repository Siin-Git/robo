"""Drawdown diagnostics (optimizer never constrains on MDD)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def max_drawdown(returns: pd.Series) -> float:
    """Maximum drawdown from a return series (negative number or 0)."""
    r = pd.Series(returns).dropna().to_numpy(dtype=float)
    if len(r) == 0:
        raise ValueError("Empty return series for drawdown")
    wealth = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(wealth)
    dd = wealth / np.maximum(peak, 1e-18) - 1.0
    return float(dd.min())
