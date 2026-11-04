import csv
from datetime import date, timedelta
from hashlib import sha256
from io import StringIO
from math import sqrt
from statistics import mean, pvariance

import pytest

from src.api.services import v8_frontier_service as svc
from src.api.services.strategy_frontier_service import comparison as existing_comparison
from .test_decisions import identity


def test_v8_matches_independent_weekly_curve_calculation():
    raw = (svc.C.ROOT / svc.ARTIFACT).read_bytes()
    period = existing_comparison()["period"]
    result = svc.calculate(raw, period)
    weeks = {}
    for row in csv.DictReader(StringIO(raw.decode())):
        day = date.fromisoformat(row["date"])
        friday = day + timedelta(days=(4-day.weekday()) % 7)
        weeks[friday] = float(row["portfolio_value_usd"])
    ordered = sorted(weeks)
    returns = [weeks[day]/weeks[prior]-1 for prior, day in zip(ordered, ordered[1:])
               if period["start"] <= day.isoformat() <= period["end"]]
    ret, vol = mean(returns)*52, sqrt(pvariance(returns)*52)
    assert len(returns) == 97
    assert result["expected_return"] == pytest.approx(ret)
    assert result["volatility"] == pytest.approx(vol)
    assert result["sharpe"] == pytest.approx((ret-.03)/vol)
    assert result["expected_return"] == pytest.approx(.4370114980754967)
    assert result["volatility"] == pytest.approx(.21264887946568894)
    assert result["artifact_sha256"] == sha256(raw).hexdigest() == "efa3bd2f0bb1b8d830f60e18d4dd0efdf5e969c7520b32ad99b419d8dde54f65"


def test_authenticated_comparison_preserves_existing_strategies(client, identity):
    cookies, _ = identity
    path = "/api/v1/strategies/v8-frontier-comparison"
    assert client.get(path, cookies={}).status_code == 401
    before = client.get("/api/v1/strategies/frontier-comparison", cookies=cookies).json()
    response = client.get(path, cookies=cookies)
    assert response.status_code == 200
    data = response.json()
    assert data["currency"] == "USD" and data["validation_status"] == "PROVISIONAL"
    assert data["data_kind"] == "BACKTEST_EQUITY_CURVE"
    assert data["period"] == before["period"]
    assert not data["actual_account_history"] and not data["optimization_eligible"] and not data["confirmation_eligible"]
    assert client.get("/api/v1/strategies/frontier-comparison", cookies=cookies).json() == before
    assert len(before["items"]) == 2


@pytest.mark.parametrize("kind", ["duplicate", "unordered", "zero", "nan", "missing_week"])
def test_reject_invalid_curve_without_filling_gaps(kind):
    raw = (svc.C.ROOT / svc.ARTIFACT).read_text()
    lines = raw.splitlines()
    if kind == "duplicate":
        lines[2] = lines[2].replace("2023-01-04", "2023-01-03")
    elif kind == "unordered":
        lines[1], lines[2] = lines[2], lines[1]
    elif kind in ("zero", "nan"):
        lines[1] = "2023-01-03," + ("0" if kind == "zero" else "NaN")
    else:
        lines = [line for line in lines if not "2025-02-03" <= line[:10] <= "2025-02-07"]
    with pytest.raises(ValueError, match="V8_"):
        svc.calculate(("\n".join(lines)+"\n").encode(), existing_comparison()["period"])


def test_v8_input_failure_does_not_break_existing_endpoint(client, identity, monkeypatch):
    cookies, _ = identity
    monkeypatch.setattr(svc, "comparison", lambda: (_ for _ in ()).throw(ValueError("V8_CURVE_INVALID")))
    assert client.get("/api/v1/strategies/v8-frontier-comparison", cookies=cookies).status_code == 503
    original = client.get("/api/v1/strategies/frontier-comparison", cookies=cookies)
    assert original.status_code == 200 and len(original.json()["items"]) == 2
