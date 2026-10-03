"""Stable read contract over Backend 1's persisted forward ledger."""
from __future__ import annotations

from bisect import bisect_right
from collections import Counter, defaultdict
from datetime import date

from sqlalchemy import select

from ...db.models.holding import Holding
from ...db.models.nav import NavDaily
from ...db.models.order import Order
from ...db.models.price import PriceDaily
from ...db.models.trade import Trade
from ..errors import ApiError, not_found
from . import _common as C
from .performance_service import _accounts


def _date_range(start: str | None, end: str | None) -> tuple[date | None, date | None]:
    try:
        start_date = C.as_date(start)
        end_date = C.as_date(end)
    except ValueError as exc:
        raise ApiError("INVALID_DATE", "start and end must use YYYY-MM-DD.", 400) from exc
    if start_date and end_date and start_date > end_date:
        raise ApiError("INVALID_DATE_RANGE", "start must be on or before end.", 400)
    return start_date, end_date


def _within(value, start: date | None, end: date | None) -> bool:
    day = C.as_date(value)
    return (start is None or day >= start) and (end is None or day <= end)


def _price_history(session, asset_ids: set[str], end: date | None) -> dict[str, list[tuple]]:
    if not asset_ids:
        return {}
    query = select(PriceDaily).where(PriceDaily.asset_id.in_(asset_ids))
    if end:
        query = query.where(PriceDaily.date <= end)
    history = defaultdict(list)
    for row in session.scalars(query.order_by(PriceDaily.asset_id, PriceDaily.date)):
        history[row.asset_id].append((C.as_date(row.date), C.fnum(row.price), row.source))
    return dict(history)


def _applied_price(history: list[tuple], valuation_date: date):
    if not history:
        return None
    idx = bisect_right([row[0] for row in history], valuation_date) - 1
    return history[idx] if idx >= 0 else None


def ledger(session, participant_id: str, start: str | None = None,
           end: str | None = None) -> dict:
    """Read holdings, cash, returns, orders and trades without deriving new state."""
    start_date, end_date = _date_range(start, end)
    personal, _ = _accounts(session, participant_id)
    if personal is None:
        raise not_found("PERSONAL_ACCOUNT_NOT_FOUND",
                        f"Participant {participant_id} has no personal account.")

    nav_rows = [row for row in session.scalars(
        select(NavDaily).where(NavDaily.account_id == personal.account_id)
        .order_by(NavDaily.date)
    ) if _within(row.date, start_date, end_date)]
    holdings = [row for row in session.scalars(
        select(Holding).where(Holding.account_id == personal.account_id)
        .order_by(Holding.date, Holding.asset_id)
    ) if _within(row.date, start_date, end_date)]
    orders = [row for row in session.scalars(
        select(Order).where(Order.account_id == personal.account_id)
        .order_by(Order.effective_at, Order.order_id)
    ) if _within(row.effective_at, start_date, end_date)]
    trades = [row for row in session.scalars(
        select(Trade).where(Trade.account_id == personal.account_id)
        .order_by(Trade.execution_at, Trade.trade_id)
    ) if _within(row.execution_at, start_date, end_date)]

    holdings_by_date = defaultdict(list)
    for row in holdings:
        holdings_by_date[C.as_date(row.date)].append(row)
    price_history = _price_history(
        session, {row.asset_id for row in holdings}, end_date
    )

    snapshots = []
    for nav in nav_rows:
        valuation_date = C.as_date(nav.date)
        positions = []
        for holding in holdings_by_date[valuation_date]:
            applied = _applied_price(price_history.get(holding.asset_id, []), valuation_date)
            if applied is None:
                price_date, price_source, price_status = None, None, "missing"
            else:
                price_date, _, price_source = applied
                if price_date == valuation_date:
                    price_status = "current"
                elif nav.nav_status == "STALE_PRICE":
                    price_status = "stale"
                else:
                    price_status = "carried_forward"
            positions.append({
                "asset_id": holding.asset_id,
                "quantity": C.fnum(holding.quantity),
                "price": C.fnum(holding.price),
                "price_date": price_date.isoformat() if price_date else None,
                "price_source": price_source,
                "price_status": price_status,
                "market_value": C.fnum(holding.market_value),
                "weight": C.fnum(holding.weight),
            })
        snapshots.append({
            "date": valuation_date.isoformat(),
            "nav": C.fnum(nav.nav),
            "nav_base100": C.fnum(nav.nav_base100),
            "cash_balance": C.fnum(nav.cash_balance),
            "daily_return": C.fnum(nav.daily_return),
            "cumulative_return": C.fnum(nav.cumulative_return),
            "nav_status": nav.nav_status,
            "stale_price_flag": bool(nav.stale_price_flag),
            "holdings": positions,
        })

    order_counts = Counter(row.status for row in orders)
    return {
        "contract_version": "ledger-read-v2",
        "data_kind": "TEST_FIXTURE" if session.scalar(select(PriceDaily.asset_id).where(PriceDaily.source.like("SYNTHETIC_TEST%")).limit(1)) is not None else "FORWARD_SIMULATION",
        "units": {"nav": "KRW", "cash_balance": "KRW", "market_value": "KRW", "nav_base100": "index_100", "returns": "fraction", "weight": "fraction"},
        "participant_id": participant_id,
        "account": {
            "account_id": personal.account_id,
            "account_type": personal.account_type,
            "status": personal.status,
            "inception_date": C.as_date(personal.inception_date).isoformat(),
        },
        "start": start_date.isoformat() if start_date else None,
        "end": end_date.isoformat() if end_date else None,
        "as_of": snapshots[-1]["date"] if snapshots else None,
        "snapshots": snapshots,
        "orders": [
            {
                "order_id": row.order_id,
                "asset_id": row.asset_id,
                "side": row.side,
                "target_weight": C.fnum(row.target_weight),
                "submitted_at": row.submitted_at.isoformat(),
                "effective_at": C.as_date(row.effective_at).isoformat(),
                "status": row.status,
                "action_required": row.status == "pending",
                "alert_type": f"{row.side}_required" if row.status == "pending" else None,
            }
            for row in orders
        ],
        "order_status_summary": {
            status: order_counts.get(status, 0)
            for status in ("pending", "executed", "cancelled")
        },
        "trades": [
            {
                "trade_id": row.trade_id,
                "order_id": row.order_id,
                "asset_id": row.asset_id,
                "execution_at": C.as_date(row.execution_at).isoformat(),
                "execution_price": C.fnum(row.execution_price),
                "quantity": C.fnum(row.quantity),
                "gross_value": C.fnum(row.gross_value),
                "transaction_cost": C.fnum(row.transaction_cost),
                "net_value": C.fnum(row.net_value),
            }
            for row in trades
        ],
    }
