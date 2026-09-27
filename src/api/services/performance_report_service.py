"""Read-only dashboard report over the recorded simulation ledger."""
from sqlalchemy import select
from ...db.models.nav import NavDaily
from ...db.models.holding import Holding
from ...db.models.trade import Trade
from ...forward.performance_report import calculate_report, PERIODS
from ..errors import ApiError
from .performance_service import _accounts
from . import _common as C


def dashboard(session, participant_id, period="ALL"):
    if period not in PERIODS:
        raise ApiError("INVALID_PERIOD", "period must be 1M, 3M, 6M, 1Y or ALL", 400)
    personal, core = _accounts(session, participant_id)
    def nav_rows(account):
        if not account:
            return []
        return [{"date": C.as_date(r.date).isoformat(), "nav": float(r.nav),
                 "cash": float(r.cash_balance), "status": r.nav_status}
                for r in session.scalars(select(NavDaily).where(NavDaily.account_id == account.account_id).order_by(NavDaily.date))]
    nav = nav_rows(personal)
    if len(nav) < 2:
        return calculate_report(nav, nav_rows(core), [], [], period)
    holds = [{"date": C.as_date(h.date).isoformat(), "asset_id": h.asset_id,
              "market_value": float(h.market_value), "price": float(h.price)}
             for h in session.scalars(select(Holding).where(Holding.account_id == personal.account_id))]
    trades = [{"date": C.as_date(t.execution_at).isoformat(), "asset_id": t.asset_id,
               "quantity": float(t.quantity), "gross_value": float(t.gross_value),
               "cost": float(t.transaction_cost)}
              for t in session.scalars(select(Trade).where(Trade.account_id == personal.account_id))]
    return calculate_report(nav, nav_rows(core), holds, trades, period)


def cumulative_contributions(session, participant_id, period="ALL"):
    """Return an explicit frontend contract over the persisted forward ledger."""
    report = dashboard(session, participant_id, period)
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
        "method": "linked_asset_pnl_over_opening_nav",
    }
