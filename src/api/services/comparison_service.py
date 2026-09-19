"""One read-only contract for demo dashboard, rankings and participant detail."""
from sqlalchemy import select

from ...db.models.user import User
from ...db.models.participant import Participant
from ...db.models.portfolio import PortfolioTarget
from ...db.models.view import View
from ...forward.metrics import perf_metrics
from ...local.capstone import EMAILS, enabled
from ..errors import ApiError
from .performance_service import _accounts, _frame
from .portfolio_service import _legs, _tickers

BASES = {"return": "cumulative_return", "excess": "excess_return",
         "mdd": "mdd", "volatility": "volatility", "sharpe": "sharpe"}


def cohort(session):
    if not enabled():
        raise ApiError("COMPARISON_NOT_AVAILABLE", "Demo comparison is not enabled.", 404)
    return list(session.scalars(select(Participant).join(User, User.participant_id == Participant.participant_id)
        .where(User.email_normalized.in_(EMAILS), Participant.status == "active")
        .order_by(Participant.participant_id)))


def detail(session, participant_id):
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
        "observations": len(pn),
        "metrics": {"nav": float(pn.nav.iloc[-1] / pn.nav.iloc[0] * 100),
            "cumulative_return": pm["cumulative_return"], "core_return": cm["cumulative_return"],
            "excess_return": pm["cumulative_return"] - cm["cumulative_return"],
            "mdd": pm["mdd"], "volatility": pm["annualized_volatility"], "sharpe": pm["sharpe"]},
        "series": [{"date": d.date().isoformat(),
                    "personalized_nav": float(pn.loc[d, "nav"] / pn.nav.iloc[0] * 100),
                    "core_nav": float(cn.loc[d, "nav"] / cn.nav.iloc[0] * 100)} for d in pn.index],
        "allocation": allocation(personal), "core_allocation": allocation(core),
    }


def rankings(session, basis="return"):
    if basis not in BASES:
        raise ApiError("INVALID_BASIS", "Choose return, excess, mdd, volatility or sharpe.", 400)
    reports = [detail(session, p.participant_id) for p in cohort(session)]
    key = BASES[basis]
    # MDD is negative: closer to zero is better. Volatility alone sorts ascending.
    reports.sort(key=lambda r: (r["metrics"][key] is None,
        (r["metrics"][key] or 0) * (1 if basis == "volatility" else -1), r["participant_id"]))
    return {"basis": basis, "total": len(reports),
        "start": reports[0]["start"] if reports else None, "end": reports[0]["end"] if reports else None,
        "items": [{"rank": i+1, **{k: r[k] for k in ("participant_id", "display_name", "themes", "metrics")}}
                  for i, r in enumerate(reports)]}
