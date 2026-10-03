"""Forward price store: KRW-denominated daily levels, audit-friendly.

Core levels come from the frozen Phase 1.6 snapshot; theme ETF levels are
fetched (USD) and converted with the same FX series. Valuation and execution
only ever read this store (never the network), which makes replay exact.
"""
from __future__ import annotations

import sqlite3

import pandas as pd

from ..data.provider import get_default_provider
from ..data.snapshot import load_snapshot

CORE_IDS = ["us_equity", "developed_ex_us", "emerging_markets", "korea_equity",
            "us_treasury", "korea_treasury", "tips", "gold", "global_reit"]
HEDGED = {"us_treasury", "tips"}


def theme_asset_id(theme_id: str) -> str:
    return f"theme:{theme_id}"


def align_daily_krw(panels: dict[str, pd.Series], fx: pd.Series,
                    hedged: set[str] | None = None, max_fill_days: int = 5) -> pd.DataFrame:
    """Mirror of Phase 1 alignment, returning DAILY KRW levels."""
    hedged = hedged or set()
    daily = pd.DataFrame({**panels, "__FX__": fx}).sort_index()
    daily = daily[daily.index.dayofweek < 5]
    filled = daily.ffill(limit=max_fill_days).dropna()
    if filled.empty:
        raise RuntimeError("no overlapping daily data")
    fx_px = filled["__FX__"]
    out = pd.DataFrame(index=filled.index)
    for aid, s in panels.items():
        if aid in hedged or aid not in filled:
            out[aid] = filled[aid]
        elif s is not None and aid in ("us_equity", "developed_ex_us", "emerging_markets",
                                       "gold", "global_reit") or aid.startswith("theme:"):
            px, fxp = filled[aid].align(fx_px, join="inner")
            out[aid] = px * fxp
        else:
            out[aid] = filled[aid]
    return out.dropna(how="any")


def upsert_prices(con: sqlite3.Connection, panel: pd.DataFrame, source: str) -> int:
    n = 0
    for aid in panel.columns:
        for dt, px in panel[aid].items():
            if pd.isna(px):
                continue
            con.execute("INSERT OR REPLACE INTO prices_daily (asset_id, date, price, source)"
                        " VALUES (?, ?, ?, ?)",
                        (aid, dt.date().isoformat(), float(px), source))
            n += 1
    con.commit()
    return n


def bootstrap_from_snapshot(con: sqlite3.Connection, snap_dir, theme_tickers: dict[str, str],
                            start: str, end: str) -> dict:
    """Load core USD prices + FX from frozen snapshot, fetch theme USD history,
    convert everything to daily KRW levels and store. Returns coverage report."""
    prices, fx, _, _, _ = load_snapshot(snap_dir)
    provider = get_default_provider()
    panels = {a: prices[a] for a in CORE_IDS}
    for theme_id, ticker in theme_tickers.items():
        panels[theme_asset_id(theme_id)] = provider.get_price_history(ticker, start, end)
    panel = align_daily_krw(panels, fx, HEDGED)
    n = upsert_prices(con, panel, source="snapshot+provider-bootstrap")
    return {"rows": n, "assets": list(panel.columns),
            "start": str(panel.index.min().date()), "end": str(panel.index.max().date())}


def refresh_live(con: sqlite3.Connection, tickers: dict[str, str]) -> dict:
    """Incremental live refresh.

    tickers maps asset_id -> Yahoo ticker, including '__FX__' -> FX ticker.
    Theme asset_ids map to their ETF tickers; core ids to Phase 1 tickers.
    Returns coverage report; assets that fail to fetch are listed as stale.
    """
    from datetime import date as _date
    provider = get_default_provider()
    end = _date.today().isoformat()
    have = {r["asset_id"]: r["m"] for r in con.execute(
        "SELECT asset_id, MAX(date) AS m FROM prices_daily GROUP BY asset_id").fetchall()}
    raw: dict[str, pd.Series] = {}
    stale = []
    for aid, ticker in tickers.items():
        start = (pd.Timestamp(have[aid]) + pd.Timedelta(days=1)).date().isoformat() \
            if aid in have else "2015-01-01"
        if start > end:
            continue
        try:
            raw[aid] = provider.get_price_history(ticker, start, end)
        except Exception:
            stale.append(aid)
    fx = raw.pop("__FX__", None)
    if fx is None:
        fx_rows = con.execute("SELECT date, price FROM prices_daily WHERE asset_id='__FX__'"
                              " ORDER BY date").fetchall()
        if not fx_rows:
            raise RuntimeError("no FX data available")
        fx = pd.Series([r["price"] for r in fx_rows],
                       index=pd.to_datetime([r["date"] for r in fx_rows]))
        stale.append("__FX__")
    # Which stored ids are USD-unhedged vs hedged vs native is resolved by the
    # aligner: theme:* and core unhedged equities convert; HEDGED set stays local.
    panels = dict(raw)
    if not panels:
        fx_new = fx[fx.index.dayofweek < 5]
        if have.get('__FX__'):
            fx_new = fx_new[fx_new.index > pd.Timestamp(have['__FX__'])]
        points = upsert_prices(con, fx_new.to_frame('__FX__'), 'live-refresh') if not fx_new.empty else 0
        return {"new_points": points, "stale": stale, "asof": end}
    tmp = align_daily_krw(panels, fx, HEDGED)
    # Never rewrite history: keep only dates beyond existing per-asset coverage.
    keep = pd.DataFrame(index=tmp.index)
    for aid in tmp.columns:
        cutoff = have.get(aid)
        col = tmp[aid].copy()
        if cutoff:
            col = col[col.index > pd.Timestamp(cutoff)]
        keep[aid] = col
    # Persist observed FX as an input too. Otherwise the next refresh has no
    # stored fallback when Yahoo returns an empty FX series on a holiday/weekend.
    # Never overwrite historical FX or change the existing conversion rules.
    fx_new = fx[fx.index.dayofweek < 5].copy()
    if have.get('__FX__'):
        fx_new = fx_new[fx_new.index > pd.Timestamp(have['__FX__'])]
    keep = keep.reindex(keep.index.union(fx_new.index))
    keep['__FX__'] = fx_new
    keep = keep.dropna(how="all")
    new_points = upsert_prices(con, keep, source="live-refresh") if not keep.empty else 0
    return {"new_points": new_points, "stale": stale, "asof": end}


def price_series(con: sqlite3.Connection, asset_id: str, end: str | None = None) -> pd.Series:
    q = "SELECT date, price FROM prices_daily WHERE asset_id = ?"
    args: tuple = (asset_id,)
    if end:
        q += " AND date <= ?"
        args = (asset_id, end)
    q += " ORDER BY date"
    rows = con.execute(q, args).fetchall()
    return pd.Series([r["price"] for r in rows],
                     index=pd.to_datetime([r["date"] for r in rows]), dtype=float)


def next_available_close(con: sqlite3.Connection, asset_id: str, effective_at: str) -> str | None:
    """First tradable close on/after the effective session (never before it)."""
    row = con.execute("SELECT MIN(date) AS d FROM prices_daily WHERE asset_id = ? AND date >= ?",
                      (asset_id, effective_at)).fetchone()
    return row["d"] if row and row["d"] else None


def price_on_or_before(con: sqlite3.Connection, asset_id: str, date: str,
                       max_lookback_days: int = 14) -> tuple[float | None, str | None, bool]:
    """Return (price, price_date, stale). None price if beyond lookback."""
    row = con.execute("SELECT date, price FROM prices_daily WHERE asset_id = ? AND date <= ?"
                      " ORDER BY date DESC LIMIT 1", (asset_id, date)).fetchone()
    if row is None:
        return None, None, True
    age = (pd.Timestamp(date) - pd.Timestamp(row["date"])).days
    return float(row["price"]), row["date"], age > max_lookback_days
