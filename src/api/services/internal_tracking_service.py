"""Internal model diagnostics. No automatic model, target or order changes."""
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
import json
import math
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import select, func

from ...db.models import PortfolioDecision as D, PriceDaily, Event
from ..errors import ApiError, not_found
from . import _common as C

SNAPSHOT_KEY = "internal_tracking"
REVIEW_EVENT = "INTERNAL_ASSET_REVIEW"
VERSION = "INTERNAL_TRACKING_V1"


def _finite(value):
    return float(value) if value is not None and math.isfinite(float(value)) else None


def snapshot(session, weights, base_weights, risk_as_of):
    """Called only at confirmation, using the same model as the existing preview."""
    from .portfolio_service import _expected_return, _cov_asof, EXPECTED_RETURN_BASIS
    from .frontier_service import get_frontier
    frontier = get_frontier()
    # Include the same base and theme legs as the portfolio preview covariance.
    ids = list(dict.fromkeys(a for a in [*base_weights, *weights] if a != "cash"))
    cov = _cov_asof(session, ids, C.as_date(risk_as_of)) if risk_as_of and ids else None
    assets = []
    for aid, weight in sorted(weights.items()):
        mu = _finite(_expected_return({aid: 1.0}, base_weights))
        variance = _finite(cov.loc[aid, aid]) if cov is not None and aid in cov.index else None
        vol = 0.0 if aid == "cash" else math.sqrt(max(variance, 0)) if variance is not None else None
        assets.append({"asset_id": aid, "confirmed_weight": float(weight),
                       "expected_return": mu, "volatility": vol,
                       "unit": "fraction_per_year", "horizon": "1Y",
                       "return_basis": EXPECTED_RETURN_BASIS,
                       "independent_theme_forecast": False if aid.startswith("theme:") else None,
                       "risk_basis": "W-FRI_52_LEDOIT_WOLF_260_WEEKS",
                       "unavailable_reason": "MODEL_DATA_UNAVAILABLE" if mu is None or vol is None else None})
    return {"version": VERSION, "capture": "AT_CONFIRMATION", "visibility": "ADMIN_ONLY",
            "risk_data_as_of": str(risk_as_of) if risk_as_of else None,
            "frontier": {"version": frontier["frontier_version"],
                "risk_model_version": frontier.get("risk_model_version"),
                "generated_at": frontier.get("generated_at"),
                "points": [{k: p[k] for k in ("frontier_id", "expected_return", "volatility")}
                           for p in frontier["points"]]},
            "assets": assets}


def _decision(session, decision_id):
    # The past-price demo has a separate ledger. Even if a future caller routes
    # it here, it cannot establish actual observation/3- or 6-month progress.
    from ...forward.replay import read_metadata
    if read_metadata(session):
        raise ApiError("REPLAY_NOT_FORWARD_OBSERVATIONS",
                       "과거 가격 재생은 최초 판단의 실제 관측 기록이 아닙니다.", 409)
    row = session.get(D, decision_id)
    if row is None:
        raise not_found("DECISION_NOT_FOUND", "판단 기록을 찾을 수 없습니다.")
    return row


def list_decisions(session, limit=50, offset=0):
    count = session.scalar(select(func.count()).select_from(D))
    rows = session.scalars(select(D).order_by(D.confirmed_at.desc(), D.decision_id)
                           .offset(offset).limit(limit))
    return {"items": [{"decision_id": d.decision_id, "participant_id": d.participant_id,
                       "version": d.version, "effective_date": C.as_date(d.effective_date).isoformat(),
                       "snapshot_status": "RECORDED" if (d.provenance_json or {}).get(SNAPSHOT_KEY)
                       else "ORIGINAL_ASSET_EXPECTATIONS_NOT_RECORDED"} for d in rows],
            "total": count, "limit": limit, "offset": offset}


def _note(event):
    p = event.payload_json
    return {"review_id": event.event_id, "recorded_at": C.as_aware_utc(event.timestamp).isoformat(),
            "reviewer_id": p["reviewer_id"], "asset_id": p["asset_id"],
            "action": p["action"], "reason": p["reason"], "observation": p["observation"],
            "changes_model_or_orders": False}


def report(session, decision_id):
    d = _decision(session, decision_id)
    captured = deepcopy((d.provenance_json or {}).get(SNAPSHOT_KEY))
    # A later confirmation can have the same effective date; that leaves the
    # superseded decision an empty observation interval, rather than backfill.
    next_d = session.scalar(select(D).where(D.account_id == d.account_id, D.version > d.version)
                            .order_by(D.version).limit(1))
    start = C.as_date(d.effective_date)
    today = C.now_utc().astimezone(ZoneInfo("Asia/Seoul")).date()
    end = today + timedelta(days=1)
    if next_d:
        end = min(end, C.as_date(next_d.effective_date))
    ids = sorted(a for a in d.weights_json if a != "cash")
    prices = session.scalars(select(PriceDaily).where(PriceDaily.asset_id.in_(ids),
                            PriceDaily.date >= start, PriceDaily.date < end)
                             .order_by(PriceDaily.date, PriceDaily.asset_id)).all()
    dates = sorted(C.as_date(day).isoformat() for day in session.scalars(
        select(PriceDaily.date).distinct().where(PriceDaily.asset_id != "__FX__",
                      PriceDaily.date >= start, PriceDaily.date < end)))
    by_asset = {aid: {} for aid in ids}
    for p in prices:
        by_asset[p.asset_id][C.as_date(p.date).isoformat()] = p
    from .performance_report_service import dashboard
    actual = dashboard(session, d.participant_id, "ALL", start=start, end_exclusive=end, anchor_latest=False)
    ledger_assets = {a["asset_id"]: a for a in actual["assets"]}
    expectations = {a["asset_id"]: a for a in (captured or {}).get("assets", [])}
    assets = []
    for aid, weight in sorted(d.weights_json.items()):
        rows = by_asset.get(aid, {})
        valid = [(day, _finite(row.price)) for day, row in rows.items()
                 if _finite(row.price) is not None and float(row.price) > 0]
        first, last = (valid[0][0], valid[-1][0]) if valid else (None, None)
        baseline = valid[0][1] if valid else None
        curve = []
        for day in dates if aid != "cash" else []:
            row = rows.get(day)
            price = _finite(row.price) if row else None
            usable = price is not None and price > 0 and baseline is not None
            curve.append({"date": day, "price": price if usable else None,
                          "index100": price / baseline * 100 if usable else None,
                          "source": row.source if row else None})
        horizons = []
        for months in (3, 6):
            due = (pd.Timestamp(first or start) + pd.DateOffset(months=months)).date().isoformat()
            reached = bool(last and last >= due)
            window = [(day, price) for day, price in valid if day <= due]
            horizons.append({"months": months, "due_date": due,
                             "due_basis": "FIRST_OBSERVED_PRICE" if first else "PROVISIONAL_EFFECTIVE_DATE",
                             "status": "NOT_APPLICABLE" if aid == "cash" else "REACHED" if reached else "NOT_REACHED",
                             "observations": len(window),
                             "observed_end": window[-1][0] if window else None,
                             "cumulative_price_return": window[-1][1] / baseline - 1
                             if reached and len(window) > 1 else None})
        invalid_dates = [day for day, row in rows.items()
                         if _finite(row.price) is None or float(row.price) <= 0]
        assets.append({"asset_id": aid, "confirmed_weight": float(weight),
                       "initial_estimate": expectations.get(aid),
                       "initial_estimate_status": "RECORDED" if aid in expectations
                       else "ORIGINAL_ASSET_EXPECTATIONS_NOT_RECORDED",
                       "price_status": "NOT_APPLICABLE_CASH" if aid == "cash" else
                       "NO_OBSERVATIONS" if not valid else "ONE_OBSERVATION" if len(valid) == 1 else "OBSERVED",
                       "price_basis": "PERSISTED_KRW_LEVEL_COST_EXCLUDED",
                       "observations": len(valid), "observed_start": first, "observed_end": last,
                       "cumulative_price_return": valid[-1][1] / baseline - 1 if len(valid) > 1 else None,
                       "missing_price_dates": [day for day in dates if day not in rows] if aid != "cash" else [],
                       "invalid_price_dates": invalid_dates, "price_curve": curve, "horizons": horizons,
                       "ledger_contribution": ledger_assets.get(aid, {}).get("contribution"),
                       "ledger_observation_start": actual["start"], "ledger_observation_end": actual["end"],
                       "comparison": {"status": "NOT_COMPARABLE", "difference": None,
                           "reason": "FORECAST_HORIZON_AND_DEFINITION_NOT_AGREED" if aid in expectations
                           else "ORIGINAL_ASSET_EXPECTATIONS_NOT_RECORDED"}})
    events = session.scalars(select(Event).where(Event.event_type == REVIEW_EVENT,
                          Event.account_id == d.account_id).order_by(Event.timestamp.desc(), Event.event_id.desc()))
    notes = [_note(e) for e in events if e.payload_json.get("decision_id") == d.decision_id]
    return {"decision_id": d.decision_id, "participant_id": d.participant_id, "version": d.version,
            "snapshot_status": "RECORDED" if captured else "ORIGINAL_ASSET_EXPECTATIONS_NOT_RECORDED",
            "snapshot": captured, "portfolio_expectations": deepcopy(d.expectations_json),
            "provenance": {k: deepcopy(v) for k, v in (d.provenance_json or {}).items() if k != SNAPSHOT_KEY},
            "as_of": today.isoformat(), "window_start": start.isoformat(), "window_end_exclusive": end.isoformat(),
            "window_status": "AWAITING_EFFECTIVE_DATE" if today < start else
            "SUPERSEDED" if next_d and C.as_date(next_d.effective_date) <= today else "ACTIVE",
            "actual_ledger": actual, "assets": assets, "reviews": notes,
            "data_kind": "TEST_FIXTURE" if any(p.source.startswith("SYNTHETIC_TEST") for p in prices)
            or actual["data_kind"] == "TEST_FIXTURE" else "FORWARD_SIMULATION",
            "observation_source": "DESIGN_FORWARD_LEDGER", "historical_replay_excluded": True,
            "visibility": "ADMIN_ONLY", "automatic_revision": False}


def record_review(session, admin_id, decision_id, asset_id, action, reason, request_key):
    from .decision_service import lock_account
    d = _decision(session, decision_id)
    if asset_id not in d.weights_json:
        raise ApiError("ASSET_NOT_IN_DECISION", "이 판단에 포함된 자산을 선택해 주세요.", 422)
    reason = reason.strip()
    if not reason:
        raise ApiError("REASON_REQUIRED", "검토 근거를 입력해 주세요.", 422)
    digest = sha256(json.dumps([decision_id, asset_id, action, reason], ensure_ascii=False).encode()).hexdigest()
    event_id = sha256(json.dumps([VERSION, admin_id, decision_id, request_key]).encode()).hexdigest()[:16]
    lock_account(session, d.account_id)
    previous = session.get(Event, event_id)
    if previous:
        if previous.event_type != REVIEW_EVENT or previous.payload_json.get("payload_hash") != digest:
            raise ApiError("IDEMPOTENCY_CONFLICT", "같은 요청 키의 검토 내용이 다릅니다.", 409)
        return _note(previous)
    observed = report(session, decision_id)
    asset = next(a for a in observed["assets"] if a["asset_id"] == asset_id)
    event = Event(event_id=event_id, event_type=REVIEW_EVENT, participant_id=d.participant_id,
                  account_id=d.account_id, timestamp=C.now_utc(), model_version=VERSION,
                  payload_json={"decision_id": decision_id, "reviewer_id": admin_id,
                      "asset_id": asset_id, "action": action, "reason": reason,
                      "payload_hash": digest, "observation": {
                          "as_of": observed["as_of"], "window_start": observed["window_start"],
                          "window_end_exclusive": observed["window_end_exclusive"],
                          "observations": asset["observations"], "observed_start": asset["observed_start"],
                          "observed_end": asset["observed_end"], "price_return": asset["cumulative_price_return"],
                          "ledger_contribution": asset["ledger_contribution"],
                          "comparison": asset["comparison"], "data_kind": observed["data_kind"]}})
    session.add(event)
    session.flush()
    return _note(event)
