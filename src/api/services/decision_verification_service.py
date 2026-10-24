"""Owner-scoped, read-only evidence for a confirmed Frontier point."""
from copy import deepcopy
from datetime import timedelta
import math
from zoneinfo import ZoneInfo

from sqlalchemy import select, func

from ...db.models import Account, NavDaily, PortfolioChoice, PortfolioDecision, PriceDaily, Event
from ...db.models.base_selection import BasePortfolioSelection
from ...db.models.scheduled_job import ScheduledJob
from ...db.models.operational import ForwardState
from ...forward.performance_report import calculate_report
from ...forward.replay import read_metadata
from . import _common as C
from .decision_service import own
from .internal_tracking_service import SNAPSHOT_KEY


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _original(session, decision):
    provenance = decision.provenance_json or {}
    selection = session.get(BasePortfolioSelection, decision.selection_id)
    # Only the linked historical selection is evidence; never look up today's Fxxx.
    if selection and selection.user_id != decision.user_id:
        selection = None
    base = deepcopy(provenance.get("base_expectations") or {})
    if not base:
        base = {"expected_return": _number(selection.expected_return) if selection else None,
                "volatility": _number(selection.volatility) if selection else None}
    base = {key: _number(base.get(key)) for key in ("expected_return", "volatility")}
    base["weights"] = deepcopy(provenance.get("base_weights", selection.weights_json if selection else {}))
    expectations = decision.expectations_json or {}
    personal = {key: (_number((expectations.get(key) or {}).get("value"))
                     if (expectations.get(key) or {}).get("available") is not False else None)
                for key in ("expected_return", "volatility")}
    personal["weights"] = deepcopy(decision.weights_json)
    # Publish only the curve coordinates, not the administrator diagnostics snapshot.
    stored = (provenance.get(SNAPSHOT_KEY) or {}).get("frontier") or {}
    points = []
    for point in stored.get("points", []):
        if not isinstance(point, dict) or not isinstance(point.get("frontier_id"), str):
            continue
        expected_return, volatility = _number(point.get("expected_return")), _number(point.get("volatility"))
        if expected_return is not None and volatility is not None and volatility >= 0:
            points.append({"frontier_id": point["frontier_id"],
                           "expected_return": expected_return, "volatility": volatility})
    return {"base": base, "personalized": personal,
            "frontier": {"version": stored.get("version"), "points": points},
            "return_basis": (expectations.get("expected_return") or {}).get("basis"),
            "risk_basis": (expectations.get("volatility") or {}).get("basis"),
            "price_data_as_of": provenance.get("price_data_as_of")}


def _actual(session, decision, start, end):
    unavailable = {"status": "UNAVAILABLE", "start": None, "end": None, "observations": 0,
                   "personalized_return": None, "core_return": None, "difference_pp": None,
                   "personalized_nav": None, "core_nav": None, "excluded_rows": 0}
    if session.get(ForwardState, "replay_run_id") or read_metadata(session):
        return {**unavailable, "reason": "과거 가격 재생 자료는 판단 이후의 계좌 실적으로 사용하지 않습니다."}
    if session.scalar(select(PriceDaily.asset_id).where(func.lower(PriceDaily.source).like("synthetic%")).limit(1)):
        return {**unavailable, "reason": "합성 테스트 자료는 계좌 실적으로 사용하지 않습니다."}
    core_version = (decision.provenance_json or {}).get("core_version")
    if not core_version:
        return {**unavailable, "reason": "당시 CORE 비교 기준의 버전 미확보"}
    core = session.scalar(select(Account).where(Account.participant_id == decision.participant_id,
                                                Account.account_type == "core"))
    if not core:
        return {**unavailable, "reason": "CORE 비교 계좌 미확보"}
    # Old events without provenance remain governed by the existing store-level
    # guards. Never invent historical lineage. Explicit non-forward evidence
    # survives a copied DB, replaced price rows, or a later model configuration.
    for event in session.scalars(select(Event).where(
            Event.event_type == "NAV_CALCULATED", Event.account_id.in_([decision.account_id, core.account_id]))):
        payload = event.payload_json or {}
        if payload.get("data_kind") in {"TEST_FIXTURE", "HISTORICAL_REPLAY"}:
            return {**unavailable, "reason": "합성·재생 NAV 이력은 이후 운용 실적으로 사용하지 않습니다."}
    rows = session.scalars(select(NavDaily).where(
        NavDaily.account_id.in_([decision.account_id, core.account_id]),
        NavDaily.date >= start, NavDaily.date < end).order_by(NavDaily.date)).all()
    by_account = {decision.account_id: {}, core.account_id: {}}
    excluded = 0
    for row in rows:
        nav = _number(row.nav)
        if (row.nav_status != "OK" or row.stale_price_flag or nav is None or nav <= 0
                or row.benchmark_version != core_version):
            excluded += 1
            continue
        by_account[row.account_id][C.as_date(row.date).isoformat()] = {
            "date": C.as_date(row.date).isoformat(), "nav": nav, "status": "OK"}
    personal, benchmark = by_account[decision.account_id], by_account[core.account_id]
    common = sorted(personal.keys() & benchmark.keys())
    if len(common) < 2:
        return {**unavailable, "observations": len(common), "excluded_rows": excluded,
                "reason": "동일 날짜의 Personalized·CORE 정상 NAV가 두 시점 이상 필요합니다."}
    # Existing closed-account return engine, with exactly the same dates for both legs.
    report = calculate_report([personal[d] for d in common], [benchmark[d] for d in common], [], [])
    metrics = report["metrics"]
    return {"status": "AVAILABLE", "reason": None, "start": common[0], "end": common[-1],
            "observations": len(common), "excluded_rows": excluded,
            "personalized_return": metrics["cumulative_return"], "core_return": metrics["benchmark_return"],
            "difference_pp": metrics["difference_pp"],
            "personalized_nav": {"start": personal[common[0]]["nav"], "end": personal[common[-1]]["nav"]},
            "core_nav": {"start": benchmark[common[0]]["nav"], "end": benchmark[common[-1]]["nav"]}}


def _valuation_job(session):
    from ...forward.job_outcome import daily_outcome
    latest_slot = select(func.max(ScheduledJob.scheduled_for)).where(ScheduledJob.job_type == "daily").scalar_subquery()
    jobs = session.scalars(select(ScheduledJob).where(
        ScheduledJob.job_type == "daily", ScheduledJob.scheduled_for == latest_slot)
        .order_by(ScheduledJob.scheduled_for.desc(), ScheduledJob.started_at.desc(), ScheduledJob.job_id.desc()))
    latest = None
    job = None
    for candidate in jobs:
        latest = latest or candidate
        if candidate.scheduled_for != latest.scheduled_for:
            break
        job = candidate
        # Empty duplicate-skip audit rows must not hide the financial outcome.
        if candidate.status != "skipped" or candidate.stats_json:
            break
    if latest is None:
        return None
    result = daily_outcome(job.status, job.stats_json or {})
    if result["valuation_completed"]:
        # Check persisted normal NAV as well as the batch's claims. Historical
        # counters alone (or deleted/stale rows) cannot establish completion.
        stats = job.stats_json or {}
        try:
            asof = C.as_date(stats.get("asof"))
        except (ValueError, TypeError, AttributeError):
            asof = None
        rows = session.scalars(select(NavDaily).where(NavDaily.date == asof)).all() if asof else []
        normal = {r.account_id for r in rows if r.nav_status == "OK" and not r.stale_price_flag
                  and _number(r.nav) is not None and _number(r.nav) > 0}
        expected = set((stats.get("account_results") or {}).keys())
        if (not normal or len(normal) < result["valuated"]
                or (expected and not expected.issubset(normal))):
            result.update(state="PARTIAL", message="정상 NAV 저장 확인 미완료", valuation_completed=False)
    return {"status": job.status, "latest_attempt_status": latest.status, "scope": "ALL_ACCOUNTS",
            "scheduled_for": C.as_date(job.scheduled_for).isoformat(),
            "completed_at": C.as_aware_utc(job.completed_at).isoformat() if job.completed_at else None,
            **result}


def verification(session, user_id, decision_id):
    decision = own(session, user_id, decision_id)
    next_decision = session.scalar(select(PortfolioDecision).where(
        PortfolioDecision.account_id == decision.account_id, PortfolioDecision.version > decision.version)
        .order_by(PortfolioDecision.version).limit(1))
    start = C.as_date(decision.effective_date)
    end = C.now_utc().astimezone(ZoneInfo("Asia/Seoul")).date() + timedelta(days=1)
    if next_decision:
        end = min(end, C.as_date(next_decision.effective_date))
    original = _original(session, decision)
    actual = _actual(session, decision, start, end)
    from ...forward.opening import EVENT as OPENING_EVENT
    inherited = session.scalar(select(Event).where(Event.event_type == OPENING_EVENT,
                               Event.account_id == decision.account_id))
    opening_context = ({"forward_start": inherited.payload_json["forward_start"],
                        "historical_start": inherited.payload_json["historical_start"],
                        "historical_end": inherited.payload_json["historical_end"]} if inherited else None)
    definition = ((decision.expectations_json or {}).get("expected_return") or {}).get("definition") or {}
    due = definition.get("end")
    complete = bool(due and actual["end"] and actual["end"] >= due and actual["start"] == definition.get("start"))
    choice = session.scalar(select(PortfolioChoice).where(
        PortfolioChoice.user_id == user_id, PortfolioChoice.decision_id == decision_id)
        .order_by(PortfolioChoice.selected_at.desc(), PortfolioChoice.choice_id.desc()).limit(1))
    return {"decision_id": decision_id, "version": decision.version,
            "valuation_job": _valuation_job(session),
            "confirmed_at": C.as_aware_utc(decision.confirmed_at).isoformat(),
            "effective_date": start.isoformat(), "reason": decision.reason,
            "superseded_effective_date": C.as_date(next_decision.effective_date).isoformat() if next_decision else None,
            "original": original, "actual": actual, "opening_context": opening_context,
            "review": {"status": "REVIEW_REQUIRED" if complete else "IN_PROGRESS",
                "horizon_end": due, "automatic_verdict": False,
                "basis": "연간 기대수익률과 단기 실현수익률의 차이로 판단의 적중 여부를 판정하지 않습니다.",
                "choice": {"action": choice.action, "reason": choice.reason,
                           "recorded_at": C.as_aware_utc(choice.selected_at).isoformat()} if choice else None},
            "read_only": True}
