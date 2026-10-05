"""Decision capture and read-only revision review; finance stays in existing engines."""
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
import json
from uuid import uuid4
from zoneinfo import ZoneInfo
import pandas as pd
from sqlalchemy import select, func, update
from ...db.models import PortfolioDecision as D, PortfolioChoice as Choice, Account, Order, PortfolioTarget, NavDaily, Trade
from ..errors import ApiError, not_found
from . import _common as C

POLICY = {"composition": "confirmed_decision_weights", "scheduled_rebalance": "continues_with_existing_band", "pending_orders": "continue", "adjust": "redesign_only_until_confirmation"}

def latest(session, account_id):
    return session.scalars(select(D).where(D.account_id == account_id).order_by(D.version.desc())).first()

def operation_context(session, account_id):
    """Calendar-effective decision, separate from the latest confirmation.

    This is a read boundary, not an assertion that an order has executed.
    Decision details retain their explicit historical windows independently.
    """
    as_of = C.now_utc().astimezone(ZoneInfo("Asia/Seoul")).date()
    rows = session.scalars(select(D).where(D.account_id == account_id).order_by(D.version.desc())).all() if account_id else []
    active = next((d for d in rows if C.as_date(d.effective_date) <= as_of), None)
    pending = next((d for d in rows if C.as_date(d.effective_date) > as_of), None)
    previous = next((d for d in rows if active and d.version < active.version), None)
    def describe(d):
        return {"decision_id": d.decision_id, "version": d.version,
                "target_effective_date": C.as_date(d.effective_date).isoformat()} if d else None
    return {"as_of": as_of.isoformat(), "selection_basis": "KST_EFFECTIVE_DATE",
            "active_decision": describe(active), "pending_decision": describe(pending),
            "previous_decision": describe(previous),
            "report_decision_id": active.decision_id if active else None,
            "status": "ACTIVE" if active else "AWAITING_INITIAL_EFFECTIVE_DATE" if pending else "LEGACY_UNRECORDED"}

def lock_account(session, account_id):
    # A write lock serializes version allocation on both SQLite and PostgreSQL.
    session.execute(update(Account).where(Account.account_id == account_id).values(status=Account.status))

def check_pending(session, account_id):
    if session.scalar(select(func.count()).select_from(Order).where(Order.account_id == account_id, Order.status == "pending")):
        raise ApiError("PENDING_ORDERS", "대기 주문 처리 후 다시 설계·확정해 주세요. 기존 주문을 자동 취소하지 않습니다.", 409)

def effective_day(now):
    day = now.astimezone(ZoneInfo("Asia/Seoul")).date() + timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day

def capture(session, user_id, pid, account, target, selection, preview, reason, adjustment_choice_id=None, rebalance_frequency=None):
    old = latest(session, account.account_id)
    from .portfolio_service import EXPECTED_RETURN_BASIS
    def metric(value, basis, frequency, name):
        return {"value": value, "unit": "fraction_per_year", "horizon": "1Y", "basis": basis,
                "sampling": frequency, "available": value is not None,
                "definition": {"start": C.as_date(target.effective_date).isoformat(),
                    "end": (pd.Timestamp(target.effective_date) + pd.DateOffset(years=1)).date().isoformat(),
                    "currency": "KRW", "cost_basis": "EXCLUDES_TRANSACTION_COSTS",
                    "dividend_basis": "PROVIDER_ADJUSTED_OR_CLOSE",
                    "return_definition": "BL_ANNUAL_STRATEGIC_RETURN" if name == "expected_return" else "WEEKLY_LEDOIT_WOLF_COVARIANCE",
                    "sampling": frequency, "portfolio_reference": None,
                    "benchmark_reference": selection.selection_id if name == "tracking_error" else "NONE"},
                "unavailable_reason": None if value is not None else "MODEL_DATA_UNAVAILABLE"}
    paths = ["outputs/latest/bl_posterior_returns.csv", "config/expected_returns_v0.yaml", "config/forward_v0.yaml", "src/forward/portfolio.py", "src/api/services/portfolio_service.py", "src/risk/covariance.py", "src/api/services/frontier_service.py", "src/api/services/internal_tracking_service.py", "outputs/api/frontier.json"]
    hashes = {p: sha256((C.ROOT/p).read_bytes()).hexdigest() for p in paths if (C.ROOT/p).exists()}
    from . import market_comparison
    if market_comparison.enabled():
        data, meta = market_comparison.bundle()
        data_version = {"version": meta.get("version"), "sha256": sha256(data.to_csv().encode()).hexdigest()}
    else:
        from ...db.models import PriceDaily
        px = session.scalars(select(PriceDaily).order_by(PriceDaily.date, PriceDaily.asset_id)).all()
        data_version = {"version": "design_price_store", "sha256": sha256(json.dumps([(str(p.date), p.asset_id, str(p.price), p.source) for p in px]).encode()).hexdigest(), "rows": len(px)}
    from .internal_tracking_service import snapshot, SNAPSHOT_KEY
    internal_snapshot = snapshot(session, target.weights_json, selection.weights_json,
                                 preview["risk_comparison"]["as_of"])
    row = D(decision_id=str(uuid4()), user_id=user_id, participant_id=pid, account_id=account.account_id,
        version=old.version + 1 if old else 1, previous_decision_id=old.decision_id if old else None,
        selection_id=selection.selection_id, target_id=target.target_id, confirmed_at=target.created_at,
        effective_date=target.effective_date, weights_json=deepcopy(target.weights_json), reason=reason,
        expectations_json={"expected_return": metric(preview["personalized"]["expected_return"], EXPECTED_RETURN_BASIS, "annual_model", "expected_return"),
            "volatility": metric(preview["personalized"]["volatility"], "5Y weekly Ledoit-Wolf annualized covariance", "W-FRI_52", "volatility"),
            "tracking_error": metric(preview["personalized"]["tracking_error"], "against selected base; weekly covariance annualized", "W-FRI_52", "tracking_error")},
        provenance_json={"frontier_version": selection.frontier_version, "frontier_id": selection.frontier_id,
            "base_weights": deepcopy(selection.weights_json), "core_version": target.core_version,
            "theme_universe_version": target.theme_universe_version, "risk_model_version": target.risk_model_version,
            "risk_comparison": preview["risk_comparison"], "artifact_sha256": hashes,
            "data_version": data_version, "price_data_as_of": preview["risk_comparison"]["as_of"], "capture": "AT_CONFIRMATION",
            "adjustment_choice_id": adjustment_choice_id, "execution_policy": POLICY,
            SNAPSHOT_KEY: internal_snapshot,
            **({"rebalance_frequency": rebalance_frequency} if rebalance_frequency else {})})
    for m in row.expectations_json.values():
        m["definition"]["portfolio_reference"] = row.decision_id
    session.add(row)
    session.flush()
    return row

def serialize(row):
    from .internal_tracking_service import SNAPSHOT_KEY
    public_provenance = {k: v for k, v in (row.provenance_json or {}).items() if k != SNAPSHOT_KEY}
    return {"decision_id": row.decision_id, "version": row.version, "user_id": row.user_id,
        "participant_id": row.participant_id, "account_id": row.account_id, "target_id": row.target_id,
        "selection_id": row.selection_id, "previous_decision_id": row.previous_decision_id,
        "confirmed_at": C.as_aware_utc(row.confirmed_at).isoformat(), "target_effective_date": C.as_date(row.effective_date).isoformat(),
        "weights": row.weights_json, "expectations": row.expectations_json, "provenance": public_provenance, "reason": row.reason}

def own(session, user_id, decision_id):
    row = session.scalar(select(D).where(D.decision_id == decision_id, D.user_id == user_id))
    if not row:
        raise not_found("DECISION_NOT_FOUND", "판단 기록을 찾을 수 없습니다.")
    return row

def list_decisions(session, user_id):
    rows = session.scalars(select(D).where(D.user_id == user_id).order_by(D.version.desc())).all()
    return {"items": [serialize(r) for r in rows], "legacy_status": None if rows else "ORIGINAL_EXPECTATIONS_NOT_RECORDED", "policy": POLICY}

def choice_json(c):
    return {"choice_id": c.choice_id, "decision_id": c.decision_id, "target_id": c.target_id, "action": c.action,
            "selected_at": C.as_aware_utc(c.selected_at).isoformat(), "reason": c.reason, "effect": c.effect_json}

def choices(session, user_id):
    return {"items": [choice_json(c) for c in session.scalars(select(Choice).where(Choice.user_id == user_id).order_by(Choice.selected_at.desc()))], "policy": POLICY}

def choose(session, user_id, decision_id, target_id, action, reason, request_key):
    payload = json.dumps([decision_id, target_id, action, reason], ensure_ascii=False)
    digest = sha256(payload.encode()).hexdigest()
    existing = session.scalar(select(Choice).where(Choice.user_id == user_id, Choice.request_key == request_key))
    if existing:
        if existing.payload_hash != digest:
            raise ApiError("IDEMPOTENCY_CONFLICT", "같은 요청 키의 내용이 다릅니다.", 409)
        return choice_json(existing)
    d = own(session, user_id, decision_id)
    lock_account(session, d.account_id)
    # Recheck after the lock for concurrent identical requests.
    existing = session.scalar(select(Choice).where(Choice.user_id == user_id, Choice.request_key == request_key))
    if existing:
        if existing.payload_hash != digest:
            raise ApiError("IDEMPOTENCY_CONFLICT", "같은 요청 키의 내용이 다릅니다.", 409)
        return choice_json(existing)
    if latest(session, d.account_id).decision_id != decision_id or d.target_id != target_id:
        raise ApiError("STALE_DECISION", "최신 확정 판단과 목표를 다시 조회해 주세요.", 409)
    if action == "ADJUST":
        check_pending(session, d.account_id)
    row = Choice(choice_id=str(uuid4()), user_id=user_id, decision_id=decision_id, target_id=target_id,
        action=action, selected_at=C.now_utc(), reason=reason, request_key=request_key, payload_hash=digest,
        effect_json={**POLICY, "target_changed": False, "orders_created": False})
    session.add(row)
    session.flush()
    return choice_json(row)

def validate_adjustment(session, user_id, account_id, choice_id):
    if not choice_id:
        return
    c = session.scalar(select(Choice).where(Choice.choice_id == choice_id, Choice.user_id == user_id, Choice.action == "ADJUST"))
    d = latest(session, account_id)
    if not c or not d or c.decision_id != d.decision_id:
        raise ApiError("STALE_DECISION", "재설계 대상이 오래되었습니다. 최신 판단에서 다시 시작해 주세요.", 409)

def review(session, user_id, decision_id):
    d = own(session, user_id, decision_id)
    next_d = session.scalar(select(D).where(D.account_id == d.account_id, D.version == d.version + 1))
    start = C.as_date(d.effective_date)
    end_exclusive = C.as_date(next_d.effective_date) if next_d else None
    calendar_end = C.now_utc().astimezone(ZoneInfo("Asia/Seoul")).date() + timedelta(days=1)
    report_end = min(end_exclusive, calendar_end) if end_exclusive else calendar_end
    first = session.scalar(select(func.min(Trade.execution_at)).where(Trade.account_id == d.account_id, Trade.execution_at >= start, Trade.execution_at < report_end))
    from .performance_report_service import dashboard
    report = dashboard(session, d.participant_id, "ALL", start=start, end_exclusive=report_end, anchor_latest=False)
    from ...forward.expectation_comparison import ledger_comparisons
    comparisons = ledger_comparisons(d.expectations_json, report, d.decision_id, d.provenance_json.get("core_version"))
    observed_start, observed_end = report["start"], report["end"]
    horizons = []
    for months in (3, 6):
        due = (pd.Timestamp(observed_start or start) + pd.DateOffset(months=months)).date().isoformat()
        reached = bool(observed_start and observed_end and observed_end >= due)
        horizon_report = dashboard(session, d.participant_id, "ALL", start=start, end_exclusive=min(report_end, (pd.Timestamp(due)+pd.Timedelta(days=1)).date()), anchor_latest=False) if reached else None
        horizons.append({"months": months, "due_date": due, "status": "REACHED" if reached else "NOT_REACHED",
            "observed_start": observed_start, "observed_end": horizon_report["end"] if horizon_report else observed_end,
            "cumulative_return": horizon_report["metrics"]["cumulative_return"] if horizon_report else None,
            "due_basis": "FIRST_VALUATION" if observed_start else "PROVISIONAL_EFFECTIVE_DATE",
            "observations": horizon_report["observations"] if horizon_report else report["observations"],
            "quality": horizon_report["quality"] if horizon_report else report["quality"]})
    from .ledger_service import status
    rb = status(session, d.participant_id)["rebalance"]
    current = {a["asset_id"]: a["current_weight"] for a in (rb or {}).get("assets", [])}
    valid = (rb or {}).get("status") == "READY"
    nav = session.get(NavDaily, (d.account_id, C.as_date((rb or {}).get("as_of")))) if (rb or {}).get("as_of") else None
    current["cash"] = float(nav.cash_balance / nav.nav) if nav and valid and nav.nav > 0 else None
    weight_changes = []
    for asset in sorted(set(d.weights_json) | set(current)):
        cw = current.get(asset, 0 if valid else None)
        tw = d.weights_json.get(asset, 0)
        weight_changes.append({"asset_id":asset,"confirmed_weight":tw,"current_weight":cw,
            "difference":cw-tw if cw is not None else None,"unit":"fraction"})
    return {"decision": serialize(d), "first_execution_date": C.as_date(first).isoformat() if first and (not end_exclusive or C.as_date(first) < end_exclusive) else None,
        "valuation_date": observed_end, "observation_start": observed_start, "observation_end": observed_end,
        "superseded_effective_date": end_exclusive.isoformat() if end_exclusive else None,
        "actual": report, "comparisons": comparisons, "weight_changes": weight_changes, "weight_changes_as_of": (rb or {}).get("as_of"), "horizons": horizons,
        "review_reasons": [report["status"]] + (["EXPECTATION_DEFINITIONS_DIFFER"] if any(c["status"] == "NOT_COMPARABLE" for c in comparisons) else []) + (["SUPERSEDED"] if next_d else []),
        "review_only": True, "policy": POLICY}
