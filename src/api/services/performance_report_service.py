"""Read-only dashboard report over the recorded simulation ledger."""
from datetime import timedelta
from sqlalchemy import select
from ...db.models.nav import NavDaily
from ...db.models.holding import Holding
from ...db.models.trade import Trade
from ...db.models.price import PriceDaily
from ...forward.performance_report import calculate_report, PERIODS
from ..errors import ApiError
from .performance_service import _accounts
from . import _common as C


def dashboard(session, participant_id, period="ALL", start=None, end_exclusive=None, anchor_latest=True):
    if period not in PERIODS:
        raise ApiError("INVALID_PERIOD", "period must be 1M, 3M, 6M, 1Y or ALL", 400)
    personal, core = _accounts(session, participant_id)
    from ...forward.replay import read_metadata
    replay = read_metadata(session)
    # Keep the keyword for historical callers, but anchor to the current
    # KST-effective decision rather than the newest (possibly future) one.
    context = None
    if anchor_latest:
        from .decision_service import operation_context
        context = operation_context(session, personal.account_id if personal else None)
        active = context["active_decision"]
        pending = context["pending_decision"]
        if replay:
            start = max(C.as_date(start), C.as_date(replay["start"])) if start else C.as_date(replay["start"])
            cutoff = C.as_date(replay["end"]) + timedelta(days=1)
            end_exclusive = min(C.as_date(end_exclusive), cutoff) if end_exclusive else cutoff
            context["selection_basis"] = "CURRENT_CONFIGURATION_HISTORICAL_REPLAY"
        elif active or pending:
            effective = C.as_date((active or pending)["target_effective_date"])
            start = max(C.as_date(start), effective) if start else effective
            cutoff = C.as_date(context["as_of"]) + timedelta(days=1)
            end_exclusive = min(C.as_date(end_exclusive), cutoff) if end_exclusive else cutoff
        context["window_start"] = start.isoformat() if start else None
        context["window_end_exclusive"] = end_exclusive.isoformat() if end_exclusive else None
    def nav_rows(account):
        if not account:
            return []
        return [{"date": C.as_date(r.date).isoformat(), "nav": float(r.nav),
                 "cash": float(r.cash_balance), "status": r.nav_status}
                for r in session.scalars(select(NavDaily).where(NavDaily.account_id == account.account_id).order_by(NavDaily.date))
                if (start is None or C.as_date(r.date) >= start) and (end_exclusive is None or C.as_date(r.date) < end_exclusive)]
    kind = "HISTORICAL_REPLAY" if replay else "TEST_FIXTURE" if session.scalar(select(PriceDaily.asset_id).where(PriceDaily.source.like("SYNTHETIC_TEST%")).limit(1)) else "FORWARD_SIMULATION"
    def calculate(*args):
        result = calculate_report(*args)
        result["data_kind"] = kind
        if replay:
            result["replay_context"] = replay
        if context is not None:
            result["decision_context"] = context
        return result
    nav = nav_rows(personal)
    if len(nav) < 2:
        return calculate(nav, nav_rows(core), [], [], period)
    holds = [{"date": C.as_date(h.date).isoformat(), "asset_id": h.asset_id,
              "market_value": float(h.market_value), "price": float(h.price)}
             for h in session.scalars(select(Holding).where(Holding.account_id == personal.account_id))]
    trades = [{"date": C.as_date(t.execution_at).isoformat(), "asset_id": t.asset_id,
               "quantity": float(t.quantity), "gross_value": float(t.gross_value),
               "cost": float(t.transaction_cost)}
              for t in session.scalars(select(Trade).where(Trade.account_id == personal.account_id))]
    return calculate(nav, nav_rows(core), holds, trades, period)


def cumulative_contributions(session, participant_id, period="ALL", report=None):
    """Return an explicit frontend contract over the persisted forward ledger."""
    report = report if report is not None else dashboard(session, participant_id, period)
    cumulative_return = report["metrics"]["cumulative_return"]
    contribution_total = sum(row["contribution"] for row in report["assets"])
    difference = (
        contribution_total - cumulative_return
        if cumulative_return is not None
        else None
    )
    return {
        "status": report["status"],
        "period": report["period"],
        "start": report["start"],
        "end": report["end"],
        "observations": report["observations"],
        "decision_context": report["decision_context"],
        "cumulative_return": cumulative_return,
        "assets": [
            {
                "asset_id": row["asset_id"],
                "group": row["group"],
                "cumulative_contribution": row["contribution"],
                "average_weight": row["average_weight"],
                "price_return": row["price_return"],
            }
            for row in report["assets"]
        ],
        "history": [
            {
                "date": point["date"],
                "cumulative_return": point["total"],
                "contributions": point["values"],
            }
            for point in report["attribution"]
        ],
        "reconciliation": {
            "contribution_total": contribution_total,
            "difference": difference,
            "reconciled": abs(difference) <= 1e-9 if difference is not None else None,
        },
        "quality": report["quality"],
        "comparison_window": report.get("comparison_window"),
        "data_kind": report["data_kind"],
        "replay_context": report.get("replay_context"),
        "method": "linked_asset_pnl_over_opening_nav",
    }
