"""Public recorded-ledger comparison; no target-weight price replay or writes.

Auth decides cohort membership, the operating database supplies valuations.
Only normalized performance is shared; account amounts, holdings, decisions and
orders stay on owner-scoped endpoints. All figures use calculate_report.
"""
from datetime import timedelta

from sqlalchemy import select, or_

from ...db.models import Account, Participant, User
from ...forward.performance_report import calculate_report, PERIODS
from ..errors import ApiError
from . import performance_report_service as reports, _common as C

BASES = {"return": "cumulative_return", "excess": "difference_pp", "mdd": "mdd", "volatility": "volatility"}


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
    individual = {}
    reasons = {}
    for person in people:
        pid = person.participant_id
        account = db.scalar(select(Account).where(Account.participant_id == pid, Account.account_type == "personal"))
        report = reports.dashboard(db, pid, period) if account else calculate_report([], [], [], [], period)
        individual[pid] = report
        context = report.get("decision_context", {})
        reasons[pid] = ("NO_CONFIRMED_DECISION" if not account or context.get("status") == "LEGACY_UNRECORDED"
                        else "AWAITING_EFFECTIVE_DATE" if not context.get("active_decision")
                        else "NO_VALUATIONS" if report["observations"] == 0
                        else "ONE_VALUATION" if report["observations"] == 1 else None)
    eligible = [pid for pid in individual if reasons[pid] is None]
    common = sorted(set.intersection(*[{p["date"] for p in individual[pid]["series"]} for pid in eligible])) if eligible else []
    reason = "INSUFFICIENT_PARTICIPANTS" if len(eligible) < 2 else "NO_COMMON_PERIOD" if len(common) < 2 else None
    # Even the charts must use the same observed dates; never interpolate a
    # participant's missing valuation or include a date before its decision.
    bounded = {}
    if common:
        for pid in eligible:
            report = reports.dashboard(db, pid, "ALL", C.as_date(common[0]),
                C.as_date(common[-1]) + timedelta(days=1), observation_dates=set(common))
            report["period"] = period
            bounded[pid] = report
    rows = []
    for person in people:
        pid = person.participant_id
        report = bounded.get(pid)
        comparable = reason is None and report is not None
        metrics = report["metrics"] if comparable else dict.fromkeys(individual[pid]["metrics"])
        row_reason = reasons[pid] or reason
        if comparable and metrics[BASES[basis]] is None:
            row_reason = "CORE_SAME_PERIOD_MISSING" if basis == "excess" else "RISK_HISTORY_INSUFFICIENT"
        rows.append({"participant_id": pid, "display_name": person.display_name,
            "rank": None, "reason": row_reason, "metrics": metrics,
            "observations": report["observations"] if report else individual[pid]["observations"],
            "observed_start": individual[pid]["start"], "observed_end": individual[pid]["end"],
            "quality": report["quality"] if report else individual[pid]["quality"],
            "start": common[0] if report else None, "end": common[-1] if report else None,
            "series": [{"date": p["date"], "personal_index100": (1+p["personal"])*100,
                        "core_index100": (1+p["benchmark"])*100 if p["benchmark"] is not None else None}
                       for p in report["series"]] if report else []})
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
    return {"data_source": "ACCOUNT_LEDGER", "data_kind": "TEST_FIXTURE" if any(
        r.get("data_kind") == "TEST_FIXTURE" for r in individual.values()) else "FORWARD_SIMULATION",
        "period": period, "basis": basis, "status": "AVAILABLE" if reason is None else "UNAVAILABLE",
        "reason": reason, "start": common[0] if common else None, "end": common[-1] if common else None,
        "dates": common, "registered": len(rows), "ranked": sum(r["rank"] is not None for r in rows),
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
    report["comparison_window"] = {k: result[k] for k in ("start", "end", "dates", "status", "reason")}
    if result["own_report"] is None:
        mine = next((row for row in result["items"] if row["participant_id"] == pid), None)
        report["comparison_window"].update(status="UNAVAILABLE",
            reason=(mine["reason"] if mine else None) or result["reason"] or "NOT_COMPARABLE_COHORT")
    return report
