"""Return slicing helpers."""
from __future__ import annotations

import pandas as pd


def slice_lookback(weekly_returns: pd.DataFrame, years: float) -> pd.DataFrame:
    n_weeks = int(round(years * 52))
    if len(weekly_returns) < n_weeks:
        raise ValueError(
            f"Not enough weekly history: have {len(weekly_returns)}, need {n_weeks} for {years}Y"
        )
    return weekly_returns.iloc[-n_weeks:].copy()
