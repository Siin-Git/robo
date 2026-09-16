from datetime import date

import numpy as np
import pandas as pd
import pytest

from src.api.services import onboarding_service as svc
from src.db.models.price import PriceDaily
from src.forward.prices import CORE_IDS


def test_preview_reports_same_model_risk_and_actual_scaled_funding(env, monkeypatch):
    weights = {aid: 0.0 for aid in CORE_IDS}
    weights.update(us_equity=0.6, us_treasury=0.4)
    point = {"frontier_id": "F_TEST", "expected_return": 0.05,
             "volatility": 0.5, "weights": [{"asset_id": k, "weight": v} for k, v in weights.items()]}
    monkeypatch.setattr(svc, "find_point", lambda _: point)
    monkeypatch.setattr(svc, "get_frontier", lambda: {"frontier_version": svc.FRONTIER_VERSION})
    ids = CORE_IDS + ["theme:ai"]
    cov = pd.DataFrame(np.diag([0.01] * len(CORE_IDS) + [4.0]), index=ids, columns=ids)
    monkeypatch.setattr(svc, "_cov_asof", lambda *args: cov)
    with env.factory() as session:
        session.add(PriceDaily(asset_id="us_equity", date=date(2026, 9, 11), price=100, source="test"))
        session.flush()
        result = svc.preview(session, "test", "test", "F_TEST", ["ai"])
    risk = result["risk_comparison"]
    assert result["risk_guardrail_applied"]
    assert risk["base_volatility"] == pytest.approx(np.sqrt(0.0052))
    assert risk["base_volatility"] != result["base"]["volatility"]
    assert risk["personalized_volatility"] - risk["base_volatility"] <= risk["max_increase_pp"] / 100 + 1e-9
    assert risk["as_of"] == "2026-09-11"
    final = {w["asset_id"]: w["weight"] for w in result["personalized"]["weights"]}
    funding = sum(w["weight"] for w in result["funding"])
    assert 0 < final["theme:ai"] < 0.1
    assert funding == pytest.approx(final["theme:ai"])
    assert funding == pytest.approx(0.6 - final["us_equity"])


def test_preview_without_prices_does_not_claim_comparable_risk(env, monkeypatch):
    weights = {aid: 0.0 for aid in CORE_IDS}
    weights.update(us_equity=0.6, us_treasury=0.4)
    monkeypatch.setattr(svc, "find_point", lambda _: {
        "frontier_id": "F_TEST", "expected_return": 0.05, "volatility": 0.08,
        "weights": [{"asset_id": k, "weight": v} for k, v in weights.items()]})
    monkeypatch.setattr(svc, "get_frontier", lambda: {"frontier_version": svc.FRONTIER_VERSION})
    with env.factory() as session:
        result = svc.preview(session, "test", "test", "F_TEST", ["ai"])
    assert result["risk_comparison"]["base_volatility"] is None
    assert result["risk_comparison"]["personalized_volatility"] is None
    assert result["risk_comparison"]["method"] is None
