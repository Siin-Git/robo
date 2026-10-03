"""Existing buy-and-hold reference convention, reusable for matching periods."""
import numpy as np
import pandas as pd

def evaluate_levels(weights, prices, start, end, minimum=2):
    if not weights or any(not np.isfinite(w) or w < 0 for w in weights.values()) or abs(sum(weights.values())-1)>1e-6:
        raise ValueError("INVALID_WEIGHTS")
    active={k:float(v) for k,v in weights.items() if v>0 and k!='cash'}
    if set(active)-set(prices.columns):
        raise ValueError("REFERENCE_ASSET_PRICES_MISSING")
    levels=prices.loc[start:end,list(active)]
    if len(levels)<minimum or str(levels.index[0].date())!=start or str(levels.index[-1].date())!=end or levels.isna().any().any() or (levels<=0).any().any():
        raise ValueError("SAME_PERIOD_PRICES_UNAVAILABLE")
    nav=((levels/levels.iloc[0]).mul(pd.Series(active)).sum(axis=1)+weights.get('cash',0))*100
    return pd.DataFrame({'nav':nav,'daily_return':nav.pct_change(fill_method=None).fillna(0)})
