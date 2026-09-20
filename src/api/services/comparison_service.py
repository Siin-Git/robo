"""One read-only contract for demo dashboard, rankings and participant detail."""
from sqlalchemy import select

from ...db.models.user import User
from ...db.models.participant import Participant
from ...db.models.portfolio import PortfolioTarget
from ...db.models.view import View
from ...forward.metrics import perf_metrics, tracking_ir
from copy import deepcopy
from datetime import timedelta
from ...local.capstone import EMAILS, enabled
from ..errors import ApiError
from .performance_service import _accounts, _frame
from .portfolio_service import _legs, _tickers

BASES = {"return": "cumulative_return", "excess": "excess_return",
         "mdd": "mdd", "volatility": "volatility", "sharpe": "sharpe",
         "te": "tracking_error", "ir": "information_ratio"}


def cohort(session):
    if not enabled():
        raise ApiError("COMPARISON_NOT_AVAILABLE", "Demo comparison is not enabled.", 404)
    return list(session.scalars(select(Participant).join(User, User.participant_id == Participant.participant_id)
        .where(User.email_normalized.in_(EMAILS), Participant.status == "active")
        .order_by(Participant.participant_id)))


def legacy_detail(session, participant_id):
    person = next((p for p in cohort(session) if p.participant_id == participant_id), None)
    if person is None:
        raise ApiError("PARTICIPANT_NOT_FOUND", "This participant is not in the demo comparison.", 404)
    personal, core = _accounts(session, participant_id)
    pn, cn = _frame(session, personal.account_id), _frame(session, core.account_id)
    if len(pn) < 31 or not pn.index.equals(cn.index):
        raise ApiError("DEMO_DATA_INCOMPLETE", "Run the capstone seed before presenting.", 409)
    # NAV is the displayed source of truth. Independently rounded persisted
    # daily_return values must not introduce drift into realized risk metrics.
    for frame in (pn, cn):
        frame["daily_return"] = frame["nav"].pct_change().fillna(0.0)
    pm, cm = perf_metrics(pn), perf_metrics(cn)
    relative = tracking_ir(pn, cn)
    monday = pn.index[-1].date() - timedelta(days=pn.index[-1].weekday())
    baseline = pn.index[pn.index.date < monday]
    weekly = None
    if len(baseline):
        wp, wc = pn.loc[baseline[-1]:], cn.loc[baseline[-1]:]
        wm, wcm = perf_metrics(wp), perf_metrics(wc)
        if "cumulative_return" in wm and "cumulative_return" in wcm:
            weekly = {"week_start": monday.isoformat(), "start": wp.index[0].date().isoformat(),
                "end": wp.index[-1].date().isoformat(), "portfolio_return": wm["cumulative_return"],
                "core_return": wcm["cumulative_return"],
                "excess_return": wm["cumulative_return"] - wcm["cumulative_return"]}

    themes = list(session.scalars(select(View.theme_id).where(View.participant_id == participant_id,
        View.status == "hold", View.end_at.is_(None)).order_by(View.view_id)))
    def allocation(account):
        target = session.scalar(select(PortfolioTarget).where(PortfolioTarget.account_id == account.account_id)
            .order_by(PortfolioTarget.effective_date.desc(), PortfolioTarget.created_at.desc()))
        return _legs(dict(target.weights_json), _tickers(session))
    return {
        "participant_id": participant_id, "display_name": person.display_name, "themes": themes,
        "benchmark": "CORE_V0.3", "data_source": "DEMO_SYNTHETIC", "risk_free_rate": 0,
        "start": pn.index[0].date().isoformat(), "end": pn.index[-1].date().isoformat(),
        "observations": len(pn), "status": "ready", "weekly": weekly,
        "core_metrics": {"cumulative_return": cm["cumulative_return"], "mdd": cm["mdd"],
            "volatility": cm["annualized_volatility"], "sharpe": cm["sharpe"]},
        "metrics": {"nav": float(pn.nav.iloc[-1] / pn.nav.iloc[0] * 100),
            "cumulative_return": pm["cumulative_return"], "core_return": cm["cumulative_return"],
            "excess_return": pm["cumulative_return"] - cm["cumulative_return"],
            "mdd": pm["mdd"], "volatility": pm["annualized_volatility"], "sharpe": pm["sharpe"],
            "tracking_error": relative["tracking_error"], "information_ratio": relative["information_ratio"], "sortino": None},
        "series": [{"date": d.date().isoformat(),
                    "personalized_nav": float(pn.loc[d, "nav"] / pn.nav.iloc[0] * 100),
                    "core_nav": float(cn.loc[d, "nav"] / cn.nav.iloc[0] * 100)} for d in pn.index],
        "allocation": allocation(personal), "core_allocation": allocation(core),
    }


def detail(session, participant_id):
    from .enrollment_service import own
    user = session.scalar(select(User).where(User.participant_id == participant_id))
    slot = own(session, user) if user else None
    from . import market_comparison
    if market_comparison.enabled():
        if not user or (not slot and participant_id not in {p.participant_id for p in cohort(session)}):
            raise ApiError("PARTICIPANT_NOT_FOUND", "비교할 참가자가 없습니다.", 404)
        return market_comparison.report(session, user, slot)
    if slot:
        if not slot.confirmed_at:
            raise ApiError("SETUP_REQUIRED", "공통 CORE와 Theme 선택을 먼저 완료해 주세요.", 409)
        config = slot.configuration_json
        report = deepcopy(slot.report_json) if slot.report_json else {
            "participant_id": participant_id, "display_name": user.participant.display_name,
            "themes": config["theme_ids"], "benchmark": config["core_id"], "status": "awaiting_performance",
            "data_source": "FORWARD_PENDING", "series": [], "metrics": None, "start": None, "end": None,
            "observations": 0, "allocation": config["allocation"], "core_allocation": config["core_allocation"],
            "weekly": None, "core_metrics": None}
        report.update(confirmed_at=slot.confirmed_at.isoformat(), forward_started_at=None,
            target_allocation=config["allocation"], allocation_basis="시연 시나리오의 고정 목표 비중 · 실제 보유 비중 아님")
        return report
    return legacy_detail(session, participant_id)


def reports(session):
    from .enrollment_service import active, slots
    group = active(session)
    people = cohort(session)
    if group:
        prepared_emails = EMAILS[:group.prepared_count]
        pids = set(session.scalars(select(User.participant_id).where(User.email_normalized.in_(prepared_emails))))
        people = [p for p in people if p.participant_id in pids]
    result = [detail(session, p.participant_id) for p in people]
    if group:
        for slot in slots(session, group):
            if slot.confirmed_at:
                result.append(detail(session, session.get(User, slot.user_id).participant_id))
    return result


def sorted_reports(items, basis):
    if basis not in BASES:
        raise ApiError("INVALID_BASIS", "Unknown ranking metric.", 400)
    key = BASES[basis]
    valid = [r for r in items if r.get("metrics") and r["metrics"].get(key) is not None]
    # Compare only the fixture's common period. Pending/other periods never rank.
    valid = [r for r in valid if (r["start"], r["end"]) == ("2026-04-01", "2026-09-11")]
    valid.sort(key=lambda r: (r["metrics"][key] * (1 if basis in ("volatility", "te") else -1), r["participant_id"]))
    ranked, previous, rank = [], None, 0
    for i, r in enumerate(valid, 1):
        value = r["metrics"][key]
        if previous is None or value != previous:
            rank = i
        ranked.append({"rank": rank, **{k: r[k] for k in ("participant_id", "display_name", "themes", "metrics")}})
        previous = value
    return ranked


def rankings(session, basis="return"):
    from .enrollment_service import active, slots
    items = reports(session)
    ranked = sorted_reports(items, basis)
    group = active(session)
    return {"data_source": items[0]["data_source"] if items else None, "basis": basis, "total": len(ranked), "registered": len(items), "capacity": 13,
        "cohort_id": group.cohort_id if group else "legacy", "reserved": sum(s.confirmed_at is None for s in slots(session, group)) if group else 0,
        "start": "2026-04-01" if ranked else None, "end": "2026-09-11" if ranked else None,
        "pending": [{k: r[k] for k in ("participant_id", "display_name", "themes")} for r in items if not r.get("metrics")],
        "items": ranked}


def analytics(session):
    items = reports(session)
    ready = [r for r in items if r.get("metrics")]
    theme_ids = sorted({t for r in ready for t in r["themes"]})
    aggregates = []
    for tid in theme_ids:
        members = [r for r in ready if tid in r["themes"]]
        aggregates.append({"theme_id": tid, "count": len(members), **{
            key: sum(r["metrics"][key] for r in members) / len(members)
            for key in ("cumulative_return", "excess_return", "mdd")}})
    return {"reports": items, "rankings": {basis: sorted_reports(items, basis) for basis in BASES},
        "theme_selectors": aggregates,
        "outperformers": sum(r["metrics"]["excess_return"] > 0 for r in ready), "comparable": len(ready),
        "contribution_status": "unavailable: synthetic NAV has no matching holdings/trades"}
