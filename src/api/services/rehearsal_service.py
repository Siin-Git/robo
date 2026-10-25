"""Read-only counterfactual of a saved pair, never an operating NAV writer."""
from copy import deepcopy

import numpy as np
from ...forward.reference_portfolio import evaluate_levels
from ...risk.drawdown import max_drawdown
from ..errors import ApiError
from . import decision_service, market_comparison
from . import _common as C


def _weights(value):
    if not isinstance(value, dict) or not value:
        return None
    if any(isinstance(w, bool) or not isinstance(w, (int, float))
           or not np.isfinite(w) or w < 0 for w in value.values()):
        return None
    return deepcopy(value) if abs(sum(value.values()) - 1) <= 1e-6 else None


def _periods(prices):
    def item(key, data, label):
        return {"id": key, "label": label, "start": str(data.index[0].date()),
                "end": str(data.index[-1].date()), "observations": len(data)}
    if len(prices) < 31:
        return []
    result = [item("all", prices, "전체 자료 기간")]
    for year, data in prices.groupby(prices.index.year):
        if len(data) >= 31:
            partial = data.index[0].month != 1 or data.index[-1].month != 12
            result.append(item(str(year), data, f"{year}년" + (" · 일부 기간" if partial else "")))
    return result


def rehearsal(session, user_id, decision_id, period="all", initial_amount=10_000_000):
    # Resolve ownership before loading any prices or disclosing saved details.
    decision = decision_service.own(session, user_id, decision_id)
    result = {"status": "UNAVAILABLE", "reason": None, "kind": "HISTORICAL_REHEARSAL",
              "actual_account_history": False, "decision_id": decision.decision_id,
              "confirmed_at": C.as_aware_utc(decision.confirmed_at).isoformat(),
              "selection_reason": decision.reason, "initial_amount": initial_amount,
              "currency": "KRW", "periods": [], "period": None,
              "base": None, "personalized": None, "series": [], "source": None,
              "method": {"allocation": "SAVED_PAIR_AT_CONFIRMATION", "execution": "BUY_AND_HOLD",
                         "fractional_units": True, "rebalancing": False,
                         "fees_and_taxes_included": False, "cash_interest": 0}}
    base = _weights((decision.provenance_json or {}).get("base_weights"))
    personal = _weights(decision.weights_json)
    if base is None or personal is None:
        result["reason"] = "확정 당시 두 구성의 유효한 비중이 모두 저장되어 있지 않아 비교할 수 없습니다."
        return result
    try:
        prices, meta = market_comparison.bundle()
    except (ApiError, OSError, ValueError, KeyError):
        result["reason"] = "가격 자료를 확인할 수 없습니다. 잠시 후 다시 조회해 주세요."
        return result
    result["source"] = {key: meta.get(key) for key in ("version", "source", "currency", "start", "end", "sha256")}
    periods = _periods(prices)
    result["periods"] = periods
    if not periods:
        result["reason"] = "같은 기간의 가격 관측이 31개 이상 필요합니다."
        return result
    selected = next((p for p in periods if p["id"] == period), None)
    if selected is None:
        raise ApiError("INVALID_REHEARSAL_PERIOD", "제공된 자료 기간을 선택해 주세요.", 422)
    result["period"] = selected
    active = {k for weights in (base, personal) for k, w in weights.items() if w > 0 and k != "cash"}
    if active - set(prices.columns):
        result["reason"] = "두 구성의 모든 자산에 대한 같은 기간 가격이 확보되지 않았습니다."
        return result
    sample = prices.loc[selected["start"]:selected["end"], sorted(active)]
    # No dropna, forward fill, asset substitution, or renormalization here.
    if not np.isfinite(sample.to_numpy()).all() or (sample <= 0).any().any():
        result["reason"] = "선택 기간에 누락되거나 유효하지 않은 자산 가격이 있습니다."
        return result
    frames = {}
    for name, weights in (("base", base), ("personalized", personal)):
        try:
            frame = evaluate_levels(weights, prices, selected["start"], selected["end"], minimum=31)
        except ValueError:
            result["reason"] = "같은 기간의 유효한 자산 가격이 부족하여 계산할 수 없습니다."
            return result
        frames[name] = frame
    for name, frame in frames.items():
        frame["value"] = frame.nav * (initial_amount / 100)
        frame["drawdown"] = frame.nav / frame.nav.cummax() - 1
        result[name] = {"weights": base if name == "base" else personal,
                        "end_value": float(frame.value.iloc[-1]),
                        "cumulative_return": float(frame.nav.iloc[-1] / frame.nav.iloc[0] - 1),
                        "max_drawdown": max_drawdown(frame.daily_return)}
    result["series"] = [{"date": str(day.date()),
        "base_value": float(frames["base"].at[day, "value"]),
        "personalized_value": float(frames["personalized"].at[day, "value"]),
        "base_drawdown": float(frames["base"].at[day, "drawdown"]),
        "personalized_drawdown": float(frames["personalized"].at[day, "drawdown"])}
        for day in frames["base"].index]
    result["status"] = "AVAILABLE"
    return result
