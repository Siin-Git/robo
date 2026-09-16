"""Risk engine for the forward test: same 5Y weekly Ledoit-Wolf convention.

Covariance is built point-in-time from the price store (weekly returns ending
at asof), so monthly refresh never uses future data.
"""
from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from ..risk.covariance import annualize_covariance, ledoit_wolf_covariance
from .prices import price_series


def weekly_returns_from_levels(levels: pd.DataFrame, rule: str = "W-FRI") -> pd.DataFrame:
    w = levels.resample(rule).last().pct_change().dropna(how="any")
    if w.empty:
        raise ValueError("empty weekly returns")
    return w


def build_cov_asof(con: sqlite3.Connection, asset_ids: list[str], asof: str,
                   lookback_years: int = 5, annualization: int = 52) -> tuple[pd.DataFrame, dict]:
    levels = pd.DataFrame({a: price_series(con, a, end=asof) for a in asset_ids}).sort_index()
    levels = levels[levels.index.dayofweek < 5]
    weekly = weekly_returns_from_levels(levels)
    need = int(lookback_years * 52)
    if len(weekly) < need:
        raise ValueError(f"only {len(weekly)} weekly obs, need {need}")
    window = weekly.iloc[-need:]
    cov = annualize_covariance(ledoit_wolf_covariance(window), annualization)
    info = {"asof": asof, "lookback_years": lookback_years,
            "window_start": str(window.index.min().date()),
            "window_end": str(window.index.max().date()), "n_weekly": len(window)}
    return cov, info


def tracking_error(w_personal: pd.Series, w_core: pd.Series, cov_annual: pd.DataFrame) -> float:
    """Annualized TE. cov must cover the union of both weight vectors (no silent zeros)."""
    a, b = w_personal.align(w_core, join="outer")
    cols = list(a.index)
    missing = [c for c in cols if c not in cov_annual.index]
    if missing:
        raise ValueError(f"covariance missing assets for TE: {missing}")
    d = (a.fillna(0.0) - b.fillna(0.0)).to_numpy(float)
    C = cov_annual.loc[cols, cols].to_numpy(float)
    return float(np.sqrt(max(d @ C @ d, 0.0)))
