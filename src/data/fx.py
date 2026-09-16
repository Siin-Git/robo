"""FX helpers: KRW conversion for USD-denominated assets."""
from __future__ import annotations

import pandas as pd


def krw_return_from_usd(usd_ret: pd.Series, fx_ret: pd.Series) -> pd.Series:
    """KRW Return_t = (1 + USD ret) * (1 + FX ret) - 1, index-aligned."""
    usd_ret, fx_ret = usd_ret.align(fx_ret, join="inner")
    return (1.0 + usd_ret) * (1.0 + fx_ret) - 1.0


def krw_price_from_usd(usd_price: pd.Series, fx: pd.Series) -> pd.Series:
    px, fx2 = usd_price.align(fx, join="inner")
    return px * fx2
