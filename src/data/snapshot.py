"""Data snapshot freeze: reproduce a run without calling the provider."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..utils.io import ensure_dir, save_json


def _to_hex_csv(df: pd.DataFrame, path) -> None:
    """Write floats as float.hex() strings: bitwise-exact on every platform
    (Windows strtod is not correctly rounded, so %.17g is insufficient)."""
    hexed = df.apply(lambda col: col.map(lambda v: v.hex() if pd.notna(v) else ""))
    hexed.to_csv(path)


def _from_hex_csv(path) -> pd.DataFrame:
    import csv

    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    header, body = rows[0], rows[1:]
    idx = pd.to_datetime([r[0] for r in body])
    data = {}
    for j, col in enumerate(header[1:], start=1):
        vals = []
        for r in body:
            cell = r[j] if j < len(r) else ""
            vals.append(float.fromhex(cell) if cell else float("nan"))
        data[col] = vals
    return pd.DataFrame(data, index=idx)


def save_snapshot(
    snap_dir,
    prices: dict[str, pd.Series],
    fx: pd.Series,
    weekly_ret: pd.DataFrame,
    weekly_px: pd.DataFrame,
    meta: dict,
) -> Path:
    d = ensure_dir(snap_dir)
    daily = pd.DataFrame({**prices, "__FX__": fx}).sort_index()
    _to_hex_csv(daily, d / "aligned_daily_prices.csv")
    _to_hex_csv(weekly_ret, d / "weekly_returns.csv")
    _to_hex_csv(weekly_px, d / "weekly_prices.csv")
    save_json(meta, d / "snapshot_meta.json")
    return d


def load_snapshot(snap_dir) -> tuple[dict[str, pd.Series], pd.Series, pd.DataFrame, pd.DataFrame, dict]:
    import json

    d = Path(snap_dir)
    daily = _from_hex_csv(d / "aligned_daily_prices.csv")
    fx = daily["__FX__"]
    prices = {c: daily[c].dropna() for c in daily.columns if c != "__FX__"}
    weekly_ret = _from_hex_csv(d / "weekly_returns.csv")
    weekly_px = _from_hex_csv(d / "weekly_prices.csv")
    with open(d / "snapshot_meta.json", encoding="utf-8") as f:
        meta = json.load(f)
    return prices, fx, weekly_ret, weekly_px, meta
