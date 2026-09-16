from datetime import date
from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest
from src.api.services import portfolio_service as svc


@pytest.mark.parametrize("has_prices", [True, False])
def test_personalized_exposes_comparable_base_risk(monkeypatch, has_prices):
    # Include an asset removed entirely from the final portfolio: it still
    # belongs in the common covariance matrix used to measure the base.
    base = {"us_equity": .6, "us_treasury": .4}
    final = {"us_treasury": .4, "theme:ai": .6}
    session = SimpleNamespace(scalars=lambda _: SimpleNamespace(first=lambda: SimpleNamespace(account_id="test")))
    monkeypatch.setattr(svc, "TargetRepository", lambda _: SimpleNamespace(latest=lambda _: SimpleNamespace(weights_json=final, effective_date=date(2026,9,11))))
    monkeypatch.setattr(svc, "_base_weights_for", lambda *args: (base, "user_selected"))
    monkeypatch.setattr(svc, "_tickers", lambda _: {"ai":"AIQ"})
    monkeypatch.setattr(svc, "_cfg", lambda: {"benchmark_version":"test"})
    monkeypatch.setattr(svc.C, "latest_price_date", lambda _: date(2026,9,11))
    monkeypatch.setattr(svc.C, "frozen_bundle", lambda: (base, {}))
    def cov_asof(_, ids, asof):
        assert set(ids) == {"us_equity", "us_treasury", "theme:ai"}
        return pd.DataFrame(np.diag([.04 if a == "theme:ai" else .01 for a in ids]), index=ids, columns=ids) if has_prices else None
    monkeypatch.setattr(svc, "_cov_asof", cov_asof)
    result = svc.personalized(session, "test", "user")
    risk = result["risk_comparison"]
    if has_prices:
        assert risk["base_volatility"] == pytest.approx(np.sqrt(.0052))
        assert risk["personalized_volatility"] == pytest.approx(np.sqrt(.016))
        assert result["expected_volatility"] == risk["personalized_volatility"]
        assert risk["as_of"] == "2026-09-11"
    else:
        assert risk["base_volatility"] is None
        assert risk["personalized_volatility"] is None
        assert risk["method"] is None
