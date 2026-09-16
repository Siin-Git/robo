"""Return tests: simple return math + KRW pipeline on synthetic data."""
import numpy as np
import pandas as pd

from src.data.preprocessing import build_krw_weekly_returns


def test_simple_return_100_to_110():
    px = pd.Series([100.0, 110.0])
    ret = px.pct_change().iloc[-1]
    assert abs(ret - 0.10) < 1e-12


def _synth_daily(start="2023-01-02", n=60):
    idx = pd.bdate_range(start, periods=n)
    rng = np.random.default_rng(0)
    prices = {}
    for aid, base in [("us_equity", 100.0), ("korea_equity", 50000.0)]:
        rets = rng.normal(0.001, 0.01, size=n)
        prices[aid] = pd.Series(base * np.cumprod(1 + rets), index=idx)
    fx = pd.Series(1300 * np.cumprod(1 + rng.normal(0, 0.002, size=n)), index=idx)
    cfg = {"assets": [
        {"asset_id": "us_equity", "currency": "USD"},
        {"asset_id": "korea_equity", "currency": "KRW"},
    ]}
    return prices, fx, cfg


def test_krw_pipeline_produces_weekly_returns():
    prices, fx, cfg = _synth_daily()
    ret, pxw, diag = build_krw_weekly_returns(prices, fx, cfg, max_fill_days=5)
    assert list(ret.columns) == ["us_equity", "korea_equity"]
    assert len(ret) > 5
    assert ret.notna().all().all()
    assert diag["n_weekly"] == len(ret)
