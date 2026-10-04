"""Public recorded-ledger comparison; no target-weight price replay or writes.

Auth decides cohort membership, the operating database supplies valuations.
Only normalized performance is shared; account amounts, holdings, decisions and
orders stay on owner-scoped endpoints. All figures use calculate_report.
"""
from datetime import timedelta
import pandas as pd

from sqlalchemy import select, or_

from ...db.models import Account, Participant, User
from ...forward.performance_report import calculate_report, PERIODS, MIN_RISK_RETURN_OBSERVATIONS
from ..errors import ApiError
from . import performance_report_service as reports, _common as C

BASES = {"return": "cumulative_return", "excess": "difference_pp", "mdd": "mdd", "volatility": "volatility"}


def risk_quality(report):
    """Describe observed estimates separately from justified risk rankings.

    Keep the calculator's MDD even across gaps: it is the worst *observed*
    drawdown, not proof that an unobserved intervening loss did not occur.
    Reuse its weekday-gap/stale-price and annualization requirements, and also
    detect missing dates actually observed by another participant in this window.
    No values are filled and no new financial thresholds are introduced.
    """
    quality = report["quality"]
    gap = ("OBSERVATION_GAPS" if quality.get("missing_comparison_dates") or quality["missing_nav_dates"]
           else "STALE_VALUATIONS" if quality["stale_observations"] else None)
    measured = report["metrics"]["mdd"] is not None
    volatility = report["metrics"]["volatility"] is not None
    return {
        "mdd": {"status": "OBSERVED_ONLY" if measured and gap else "AVAILABLE" if measured else "UNAVAILABLE",
                "rankable": measured and gap is None,
                "reason": gap if measured else "MDD_HISTORY_INSUFFICIENT"},
        "volatility": {"status": "AVAILABLE" if volatility and gap is None else "UNAVAILABLE",
                       "rankable": volatility and gap is None,
                       "reason": gap or (None if volatility else "RISK_HISTORY_INSUFFICIENT"),
                       "return_observations": max(0, report["observations"] - 1),
                       "minimum_return_observations": MIN_RISK_RETURN_OBSERVATIONS},
    }


def members(auth_db):
    query = select(Participant).join(User, User.participant_id == Participant.participant_id).where(
        Participant.status == "active", User.status == "active", User.role == "user")
    from ...local.capstone import enabled, EMAILS
    if enabled():
        from .enrollment_service import active, slots
        group = active(auth_db)
        if group:
            ids = [s.user_id for s in slots(auth_db, group)]
            query = query.where(or_(User.user_id.in_(ids),
                User.email_normalized.in_(EMAILS[:group.prepared_count])))
        else:
            query = query.where(User.email_normalized.in_(EMAILS))
    return list(auth_db.scalars(query.order_by(Participant.participant_id)))


def overview(auth_db, db, period="ALL", basis="return", own_pid=None):
    if period not in PERIODS:
        raise ApiError("INVALID_PERIOD", "period must be 1M, 3M, 6M, 1Y or ALL", 400)
    if basis not in BASES:
        raise ApiError("INVALID_BASIS", "Unknown ledger ranking metric.", 400)
    people = members(auth_db)
    from ...forward.replay import read_metadata
    replay = read_metadata(db)
    individual = {}
    reasons = {}
    for person in people:
        pid = person.participant_id
        account = db.scalar(select(Account).where(Account.participant_id == pid, Account.account_type == "personal"))
        report = reports.dashboard(db, pid, period) if account else calculate_report([], [], [], [], period)
        individual[pid] = report
        context = report.get("decision_context", {})
        reasons[pid] = ("NO_CONFIRMED_DECISION" if not account or context.get("status") == "LEGACY_UNRECORDED"
                        else "AWAITING_EFFECTIVE_DATE" if not context.get("active_decision") and not replay
                        else "NO_VALUATIONS" if report["observations"] == 0
                        else "ONE_VALUATION" if report["observations"] == 1 else None)
    eligible = [pid for pid in individual if reasons[pid] is None]
    endpoints = sorted(set.intersection(*[{p["date"] for p in individual[pid]["series"]} for pid in eligible])) if eligible else []
    reason = "INSUFFICIENT_PARTICIPANTS" if len(eligible) < 2 else "NO_COMMON_PERIOD" if len(endpoints) < 2 else None
    if replay and (replay["status"] != "COMPLETE" or len(people) != replay["required"]):
        reason = "REPLAY_INCOMPLETE"
    # Align observed endpoints only. Interior evaluations must not be discarded:
    # doing so hides drawdowns and changes every path-dependent risk statistic.
    bounded = {}
    if endpoints:
        for pid in eligible:
            report = reports.dashboard(db, pid, "ALL", C.as_date(endpoints[0]),
                C.as_date(endpoints[-1]) + timedelta(days=1))
            report["period"] = period
            bounded[pid] = report
    # Also retain weekday gap markers when *everyone* missed an interior day.
    # This is the calculator's existing weekday-gap convention, not an exchange
    # holiday calendar or a new imputed NAV observation.
    weekdays = {d.date().isoformat() for d in pd.bdate_range(endpoints[0], endpoints[-1])} if endpoints else set()
    dates = sorted({p["date"] for report in bounded.values() for p in report["series"]} | weekdays) or endpoints
    for report in bounded.values():
        observed = {p["date"] for p in report["series"]}
        report["quality"]["missing_comparison_dates"] = [d for d in dates if d not in observed]
        report["metric_quality"] = risk_quality(report)
    rows = []
    for person in people:
        pid = person.participant_id
        report = bounded.get(pid)
        comparable = reason is None and report is not None
        metrics = report["metrics"] if comparable else dict.fromkeys(individual[pid]["metrics"])
        row_reason = reasons[pid] or reason
        if comparable and metrics[BASES[basis]] is None:
            row_reason = "CORE_SAME_PERIOD_MISSING" if basis == "excess" else "RISK_HISTORY_INSUFFICIENT"
        if comparable and basis in ("mdd", "volatility") and not report["metric_quality"][basis]["rankable"]:
            row_reason = report["metric_quality"][basis]["reason"]
        points = {p["date"]: p for p in report["series"]} if report else {}
        rows.append({"participant_id": pid, "display_name": person.display_name,
            "rank": None, "reason": row_reason, "metrics": metrics,
            "observations": report["observations"] if report else individual[pid]["observations"],
            "observed_start": individual[pid]["start"], "observed_end": individual[pid]["end"],
            "quality": report["quality"] if report else individual[pid]["quality"],
            "metric_quality": report["metric_quality"] if report else risk_quality(calculate_report([], [], [], [])),
            "start": endpoints[0] if report else None, "end": endpoints[-1] if report else None,
            "series": [{"date": d, "personal_index100": (1+points[d]["personal"])*100 if d in points else None,
                        "core_index100": (1+points[d]["benchmark"])*100 if d in points and points[d]["benchmark"] is not None else None}
                       for d in dates] if report and report["observations"] >= 2 else []})
    ranked = sorted([r for r in rows if r["reason"] is None and r["metrics"][BASES[basis]] is not None],
        key=lambda r: (r["metrics"][BASES[basis]] * (1 if basis == "volatility" else -1), r["participant_id"]))
    previous, rank = None, 0
    # A metric available for just one participant does not make a comparison.
    if len(ranked) >= 2:
        for i, row in enumerate(ranked, 1):
            value = row["metrics"][BASES[basis]]
            if previous is None or value != previous:
                rank = i
            row["rank"], previous = rank, value
    elif reason is None:
        reason = "INSUFFICIENT_COMPARABLE_METRIC"
        for row in ranked:
            row["reason"] = reason
    return {"data_source": "ACCOUNT_LEDGER", "replay_context": replay, "data_kind": "HISTORICAL_REPLAY" if replay else "TEST_FIXTURE" if any(
        r.get("data_kind") == "TEST_FIXTURE" for r in individual.values()) else "FORWARD_SIMULATION",
        "period": period, "basis": basis, "status": "AVAILABLE" if reason is None else "UNAVAILABLE",
        "reason": reason, "start": endpoints[0] if endpoints else None, "end": endpoints[-1] if endpoints else None,
        "dates": dates, "registered": len(rows), "ranked": sum(r["rank"] is not None for r in rows),
        "items": sorted(rows, key=lambda r: (r["rank"] is None, r["rank"] or 0, r["participant_id"])),
        "own_report": bounded.get(own_pid) if reason is None else None,
        "units": {"returns": "fraction", "series": "index100", "volatility": "fraction_per_year"},
        "benchmark": "CORE_V0.3", "method": "recorded_nav_change_no_external_flows"}


def common_dashboard(auth_db, db, pid, period):
    result = overview(auth_db, db, period, own_pid=pid)
    report = result["own_report"]
    if report is None:
        individual = reports.dashboard(db, pid, period)
        report = calculate_report([], [], [], [], period)
        report["decision_context"] = individual["decision_context"]
        report["data_kind"] = individual["data_kind"]
        if individual.get("replay_context"):
            report["replay_context"] = individual["replay_context"]
    report["comparison_window"] = {k: result[k] for k in ("start", "end", "dates", "status", "reason")}
    if result["own_report"] is None:
        mine = next((row for row in result["items"] if row["participant_id"] == pid), None)
        report["comparison_window"].update(status="UNAVAILABLE",
            reason=(mine["reason"] if mine else None) or result["reason"] or "NOT_COMPARABLE_COHORT")
    return report
