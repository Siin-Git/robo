"""Calendar alignment + weekly KRW returns."""
from __future__ import annotations

import pandas as pd

from .fx import krw_return_from_usd


def build_krw_weekly_returns(
    prices: dict[str, pd.Series],
    fx: pd.Series,
    assets_cfg: dict,
    max_fill_days: int = 5,
    weekly_rule: str = "W-FRI",
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Align daily prices, forward-fill (limited), resample weekly, compute returns.

    FX treatment per asset (assets_cfg `fx_treatment`, default by currency):
      - unhedged: KRW = (1 + USD ret) * (1 + FX ret) - 1
      - hedged:   simplified KRW-hedged proxy = local USD return (no FX leg)
      - na:       local return as-is (KRW assets)

    Returns (weekly_returns, weekly_prices, diagnostics).
    """
    order = [a["asset_id"] for a in assets_cfg["assets"]]
    treatment = {}
    for a in assets_cfg["assets"]:
        t = a.get("fx_treatment")
        if t is None:  # backward compatible default
            t = "unhedged" if a["currency"] == "USD" else "na"
        treatment[a["asset_id"]] = t
    hedged_assets = {k for k, v in treatment.items() if v == "hedged"}
    unhedged_assets = {k for k, v in treatment.items() if v == "unhedged"}

    daily = pd.DataFrame({**prices, "__FX__": fx}).sort_index()
    # FX quotes 7 days a week; keep Mon-Fri only so weekend indicative FX
    # quotes cannot fabricate a spurious trailing week in W-FRI resampling.
    daily = daily[daily.index.dayofweek < 5]
    n_before = len(daily)
    missing_before = daily.isna().sum().to_dict()

    filled = daily.ffill(limit=max_fill_days)
    missing_after = filled.isna().sum().to_dict()
    # Rows that still contain NaN after limited fill = long gaps.
    filled = filled.dropna()
    if filled.empty:
        raise RuntimeError("No overlapping daily data after limited forward-fill")

    weekly_px = filled.resample(weekly_rule).last()
    weekly_ret = weekly_px.pct_change()

    fx_w_ret = weekly_ret["__FX__"]
    out = pd.DataFrame(index=weekly_ret.index)
    for aid in order:
        if aid in unhedged_assets:
            out[aid] = krw_return_from_usd(weekly_ret[aid], fx_w_ret)
        else:
            # hedged proxy (local USD return) and KRW-native assets alike.
            out[aid] = weekly_ret[aid]
    out = out.dropna(how="any")
    if out.empty:
        raise RuntimeError("Weekly KRW returns are empty after alignment")

    weekly_prices_krw = pd.DataFrame(index=weekly_px.index)
    fx_w_px = weekly_px["__FX__"]
    for aid in order:
        if aid in unhedged_assets:
            px, fxp = weekly_px[aid].align(fx_w_px, join="inner")
            weekly_prices_krw[aid] = px * fxp
        else:
            weekly_prices_krw[aid] = weekly_px[aid]
    weekly_prices_krw = weekly_prices_krw.loc[out.index]

    diag = {
        "daily_rows_before": int(n_before),
        "daily_start": str(filled.index.min().date()),
        "daily_end": str(filled.index.max().date()),
        "weekly_start": str(out.index.min().date()),
        "weekly_end": str(out.index.max().date()),
        "n_weekly": int(len(out)),
        "missing_daily_before_fill": {k: int(v) for k, v in missing_before.items()},
        "missing_daily_after_fill": {k: int(v) for k, v in missing_after.items()},
        "fx_treatment": dict(treatment),
    }
    return out[order], weekly_prices_krw[order], diag
