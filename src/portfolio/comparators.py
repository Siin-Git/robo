"""Benchmark comparator portfolios (reference only, not primary)."""
from __future__ import annotations

import pandas as pd

from .constraints import EQUITY_GROUP, REAL_GROUP

DEFENSIVE_GROUP = ["us_treasury", "korea_treasury", "tips", "gold", "global_reit"]


def equal_weight(order) -> pd.Series:
    n = len(order)
    return pd.Series([1.0 / n] * n, index=list(order))


def sixty_forty(order) -> pd.Series:
    """Equity sleeve 60% (equal within), defensive sleeve 40% (equal within)."""
    w = {}
    for a in order:
        if a in EQUITY_GROUP:
            w[a] = 0.60 / len(EQUITY_GROUP)
        elif a in DEFENSIVE_GROUP:
            w[a] = 0.40 / len(DEFENSIVE_GROUP)
        else:
            raise ValueError(f"Asset {a} not in any 60/40 sleeve")
    return pd.Series([w[a] for a in order], index=list(order))
