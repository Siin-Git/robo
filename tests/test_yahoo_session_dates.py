"""Captured public chart responses; CI never calls Yahoo."""
from copy import deepcopy
import io
import json
from pathlib import Path
import urllib.parse

import pandas as pd
import pytest

from src.data.provider import _fetch_yahoo_chart, _to_unix_ts, _yahoo_daily_series

FIXTURES = Path(__file__).parent / "data" / "yahoo"


def response(name):
    fixture = json.loads((FIXTURES / f"{name}.json").read_text())
    return fixture, fixture["response"]["chart"]["result"][0]


def series(name):
    fixture, node = response(name)
    return _yahoo_daily_series(node, node["meta"]["symbol"],
                               _to_unix_ts(fixture["requested_start"]), _to_unix_ts(fixture["requested_end"]))


def test_original_september_18_fx_bar_keeps_its_london_session():
    fixture, node = response("fx_september_bst")
    timestamps = pd.to_datetime(node["timestamp"], unit="s", utc=True)
    position = list(timestamps).index(pd.Timestamp("2026-09-17T23:00:00Z"))
    assert timestamps[position].date().isoformat() == "2026-09-17"  # old bug
    actual = series("fx_september_bst")
    assert actual.loc["2026-09-18"] == node["indicators"]["quote"][0]["close"][position]
    assert actual.loc["2026-09-18"] == pytest.approx(1379.530029296875)
    assert "2026-09-20" not in actual.index
    assert actual.attrs['date_basis'] == 'EXCHANGE_SESSION_DATE_V1'
    assert actual.attrs['session_timezone'] == 'Europe/London'


@pytest.mark.parametrize("fixture,before,after,offset_before,offset_after", [
    ("fx_spring_dst", "2025-03-28", "2025-03-31", 0, 1),
    ("fx_autumn_dst", "2025-10-24", "2025-10-27", 1, 0),
    ("us_spring_dst", "2025-03-07", "2025-03-10", -5, -4),
    ("us_autumn_dst", "2025-10-31", "2025-11-03", -4, -5),
])
def test_iana_timezone_handles_both_dst_boundaries(fixture, before, after, offset_before, offset_after):
    _, node = response(fixture)
    local = pd.to_datetime(node["timestamp"], unit="s", utc=True).tz_convert(node["meta"]["exchangeTimezoneName"])
    bars = {timestamp.date().isoformat(): timestamp for timestamp in local}
    assert bars[before].utcoffset().total_seconds() == offset_before * 3600
    assert bars[after].utcoffset().total_seconds() == offset_after * 3600
    actual = series(fixture)
    assert before in actual.index and after in actual.index
    assert actual.index.tz is None and actual.index.equals(actual.index.normalize())


@pytest.mark.parametrize("fixture,zone", [("korea_etf","Asia/Seoul"),("us_etf","America/New_York")])
def test_korean_and_us_sessions_are_not_shifted_by_a_blanket_day(fixture, zone):
    _, node = response(fixture)
    actual = series(fixture)
    assert actual.attrs["session_timezone"] == zone
    assert list(actual.index.strftime("%Y-%m-%d")) == ["2026-09-16","2026-09-17","2026-09-18","2026-09-21","2026-09-22"]
    utc = pd.to_datetime(node["timestamp"], unit="s", utc=True).tz_localize(None).normalize()
    assert set(actual.index) <= set(utc)  # these daily bars already share UTC calendar dates
    adjusted = node["indicators"]["adjclose"][0]["adjclose"]
    local = pd.to_datetime(node["timestamp"], unit="s", utc=True).tz_convert(zone)
    expected = {stamp.date().isoformat(): value for stamp, value in zip(local, adjusted)}
    assert actual.loc["2026-09-18"] == expected["2026-09-18"]


def test_fetch_margin_includes_first_bst_session_and_filters_requested_bounds(monkeypatch):
    fixture, node = response("fx_september_bst")
    requests = []
    def open_fixture(request, **kwargs):
        requests.append(urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query))
        return io.BytesIO(json.dumps(fixture["response"]).encode())
    monkeypatch.setattr("urllib.request.urlopen", open_fixture)
    actual = _fetch_yahoo_chart("KRW=X", "2026-09-18", "2026-09-21")
    assert list(actual.index.strftime("%Y-%m-%d")) == ["2026-09-18","2026-09-21"]
    assert int(requests[0]["period1"][0]) < _to_unix_ts("2026-09-18")


@pytest.mark.parametrize("timezone", [None, "not/an/iana-zone", 3600])
def test_missing_timezone_fails_instead_of_guessing_fixed_offset(timezone):
    fixture, original = response("fx_september_bst")
    node = deepcopy(original)
    node["meta"]["exchangeTimezoneName"] = timezone
    with pytest.raises(RuntimeError, match="session timezone"):
        _yahoo_daily_series(node, "KRW=X", _to_unix_ts(fixture["requested_start"]), _to_unix_ts(fixture["requested_end"]))
