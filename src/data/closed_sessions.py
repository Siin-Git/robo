"""Only completed observed sessions; independent of the scheduler's start time."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import math

from .provider import YahooChartProvider, NoPriceData


class ClosedSessionProvider:
    def __init__(self, source=None, now=None):
        self.source = source or YahooChartProvider()
        self.now = now or datetime.now(timezone.utc)
        if self.now.tzinfo is None:
            raise ValueError("An aware collection time is required")
        self.pending = {}
        self.empty = []

    def get_price_history(self, ticker, start, end):
        try:
            series = self.source.get_price_history(ticker, start, end)
        except NoPriceData:
            self.empty.append(ticker)
            raise
        zone = ZoneInfo(series.attrs['session_timezone'])
        today = self.now.astimezone(zone).date()
        period = series.attrs.get('regular_session', {})
        period_day = close = None
        if period.get('end', 0) > period.get('start', 0) > 0:
            period_day = datetime.fromtimestamp(period['start'], zone).date()
            close = datetime.fromtimestamp(period['end'], timezone.utc) + timedelta(minutes=30)
        dates = series.index.date
        eligible = []
        for day in dates:
            final = day < today
            # Never freeze an in-progress overnight session just at midnight.
            if day == period_day and close and self.now < close:
                final = False
            # FX daily bars wait for the next London date, even if vendor
            # intraday market metadata says a shorter session has ended.
            if day == today and not ticker.endswith('=X'):
                final = bool(day == period_day and close and self.now >= close)
            eligible.append(final)
        self.pending[ticker] = sum(not yes for yes in eligible)
        result = series.loc[eligible]
        if any(not math.isfinite(float(value)) or value <= 0 for value in result):
            raise ValueError(f"Invalid observed price for {ticker}")
        return result
