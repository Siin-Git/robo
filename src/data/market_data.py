"""Fetch daily prices for the whole asset universe + FX."""
from __future__ import annotations

import pandas as pd

from .provider import MarketDataProvider, YFinanceProvider, get_default_provider


def fetch_universe_daily(
    assets_cfg: dict,
    start,
    end,
    provider: MarketDataProvider | None = None,
) -> tuple[dict[str, pd.Series], pd.Series, dict[str, str]]:
    """Fetch daily adjusted prices.

    Returns (prices_by_asset, fx_series, tickers_map).
    Raises on any missing asset (never substitutes mock data).
    """
    provider = provider or get_default_provider()
    prices: dict[str, pd.Series] = {}
    tickers: dict[str, str] = {}
    for asset in assets_cfg["assets"]:
        aid = asset["asset_id"]
        ticker = asset["ticker"]
        tickers[aid] = ticker
        try:
            s = provider.get_price_history(ticker, start, end)
        except Exception:
            # One retry via yfinance before giving up (still real data).
            fb = YFinanceProvider()
            s = fb.get_price_history(ticker, start, end)
        if s is None or len(s) == 0:
            raise RuntimeError(f"Missing price data for {aid} ({ticker})")
        prices[aid] = s
    fx_ticker = assets_cfg["fx"]["ticker"]
    tickers["FX_USDKRW"] = fx_ticker
    try:
        fx = provider.get_price_history(fx_ticker, start, end)
    except Exception:
        fx = YFinanceProvider().get_price_history(fx_ticker, start, end)
    if fx is None or len(fx) == 0:
        raise RuntimeError(f"Missing FX data for {fx_ticker}")
    return prices, fx, tickers
