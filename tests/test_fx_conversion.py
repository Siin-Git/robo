"""FX conversion: KRW = (1+USD)(1+FX) - 1."""
import pandas as pd

from src.data.fx import krw_return_from_usd


def test_fx_conversion_formula():
    usd = pd.Series([0.10, -0.05, 0.0])
    fx = pd.Series([0.02, 0.01, -0.03])
    out = krw_return_from_usd(usd, fx)
    expected = (1 + usd) * (1 + fx) - 1
    pd.testing.assert_series_equal(out, expected)


def test_fx_zero_is_identity():
    usd = pd.Series([0.05, 0.02])
    fx = pd.Series([0.0, 0.0])
    pd.testing.assert_series_equal(krw_return_from_usd(usd, fx), usd)
