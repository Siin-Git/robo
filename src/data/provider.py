"""Market data provider interface + Yahoo implementations.

V0 uses free Yahoo Finance daily adjusted prices via the public chart API.
No mock prices are ever returned: failures raise.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd


class NoPriceData(RuntimeError):
    """The provider answered successfully but has no bars in this interval."""


class MarketDataProvider(ABC):
    @abstractmethod
    def get_price_history(self, ticker: str, start, end) -> pd.Series:
        """Return daily levels indexed by naive exchange-session dates, not instants."""
        raise NotImplementedError


def _to_unix_ts(d) -> int:
    if isinstance(d, (int, float)):
        return int(d)
    ts = pd.Timestamp(d)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return int(ts.timestamp())


def _yahoo_daily_series(node: dict, ticker: str, start_ts: int, end_ts: int) -> pd.Series:
    """Interpret each daily bar in its source's IANA session timezone.

    A London midnight during BST is the previous UTC day. The timezone must
    therefore be applied before dropping it; a fixed GMT offset cannot handle DST.
    These indexes are valuation session labels, never order/fill timestamps.
    """
    name = node.get("meta", {}).get("exchangeTimezoneName")
    try:
        session_zone = ZoneInfo(name) if isinstance(name, str) else None
    except (ValueError, ZoneInfoNotFoundError):
        session_zone = None
    if session_zone is None:
        raise RuntimeError(f"Missing or invalid session timezone for {ticker}")
    stamps = node.get("timestamp") or []
    indicators = node.get("indicators", {})
    quote = (indicators.get("quote") or [{}])[0]
    adj = (indicators.get("adjclose") or [{}])[0].get("adjclose")
    values = adj if adj and any(v is not None for v in adj) else quote.get("close")
    if not stamps or values is None:
        raise NoPriceData(f"Empty price series for ticker {ticker}")
    idx = pd.to_datetime(stamps, unit="s", utc=True).tz_convert(session_zone).tz_localize(None).normalize()
    series = pd.Series(values, index=idx, dtype="float64", name=ticker).dropna()
    series = series[~series.index.duplicated(keep="last")].sort_index()
    first = pd.Timestamp(start_ts, unit="s", tz="UTC").tz_localize(None).normalize()
    last = pd.Timestamp(end_ts, unit="s", tz="UTC").tz_localize(None).normalize()
    series = series.loc[(series.index >= first) & (series.index <= last)]
    if series.empty:
        raise NoPriceData(f"Empty price series after cleaning for {ticker}")
    series.attrs.update(date_basis="EXCHANGE_SESSION_DATE_V1", session_timezone=name)
    regular = node.get("meta", {}).get("currentTradingPeriod", {}).get("regular", {})
    if isinstance(regular.get("start"), (int, float)) and isinstance(regular.get("end"), (int, float)):
        series.attrs["regular_session"] = {k: regular[k] for k in ("start", "end")}
    return series


def _fetch_yahoo_chart(ticker: str, start, end, retries: int = 3) -> pd.Series:
    start_ts = _to_unix_ts(start)
    # end exclusive: add one day so the last trading day is included
    end_ts = _to_unix_ts(end) + 86400
    enc = urllib.parse.quote(ticker, safe=".=^")
    hosts = ["query1.finance.yahoo.com", "query2.finance.yahoo.com"]
    last_err: Exception | None = None
    for host in hosts:
        url = (
            f"https://{host}/v8/finance/chart/{enc}"
            # Fetch a boundary margin, then filter *session dates*. Otherwise a
            # BST midnight on the requested first day falls before UTC period1.
            f"?period1={start_ts - 86400}&period2={end_ts + 86400}&interval=1d"
            f"&events=div%7Csplit&includeAdjustedClose=true"
        )
        for attempt in range(retries):
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    raw = resp.read()
                payload = json.loads(raw)
                chart = payload.get("chart", {})
                if chart.get("error"):
                    raise RuntimeError(f"Yahoo error for {ticker}: {chart['error']}")
                result = chart.get("result")
                if not result:
                    raise RuntimeError(f"No data returned for ticker {ticker}")
                return _yahoo_daily_series(result[0], ticker, start_ts, end_ts - 86400)
            except NoPriceData:
                raise  # Holidays/empty intervals are not transport failures.
            except Exception as exc:  # noqa: BLE001 - want explicit retry then raise
                last_err = exc
                time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {ticker} from Yahoo chart API: {last_err}")


class YahooChartProvider(MarketDataProvider):
    """Direct Yahoo chart v8 provider (no yfinance dependency)."""

    def get_price_history(self, ticker: str, start, end) -> pd.Series:
        return _fetch_yahoo_chart(ticker, start, end)


class YFinanceProvider(MarketDataProvider):
    """Optional yfinance-backed provider (fallback/alternative)."""

    def get_price_history(self, ticker: str, start, end) -> pd.Series:
        try:
            import yfinance as yf
        except ImportError as exc:
            raise RuntimeError("yfinance is not installed") from exc
        df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=False)
        if df is None or df.empty:
            raise RuntimeError(f"No data returned for ticker {ticker} via yfinance")
        col = "Adj Close" if "Adj Close" in df.columns else "Close"
        s = df[col]
        if isinstance(s, pd.DataFrame):
            s = s.iloc[:, 0]
        s = pd.Series(s.values, index=pd.to_datetime(s.index).tz_localize(None).normalize())
        s = s[s.notna()].sort_index()
        if s.empty:
            raise RuntimeError(f"Empty price series for ticker {ticker} via yfinance")
        return s


def get_default_provider() -> MarketDataProvider:
    return YahooChartProvider()
