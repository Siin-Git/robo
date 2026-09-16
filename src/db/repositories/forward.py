"""Thin repositories over SQLAlchemy sessions (no business logic here).

Append-only tables (trades, events, nav_daily, holdings_daily,
performance_daily) expose insert + read only — no update/delete methods exist
by design.
"""
from __future__ import annotations

from sqlalchemy import func, select

from ..models.account import Account
from ..models.event import Event
from ..models.nav import NavDaily
from ..models.operational import Counter
from ..models.order import Order
from ..models.participant import Participant
from ..models.portfolio import PortfolioTarget
from ..models.price import PriceDaily
from ..models.theme import Theme
from ..models.trade import Trade
from ..models.view import View


def next_id(session, prefix: str, width: int = 3) -> str:
    """Counter-based string IDs (same P001/E000001 convention as the engine)."""
    row = session.get(Counter, prefix)
    n = (int(row.value) + 1) if row else 1
    if row is None:
        session.add(Counter(name=prefix, value=n))
    else:
        row.value = n
    return f"{prefix}{n:0{width}d}"


class ParticipantRepository:
    def __init__(self, session):
        self.s = session

    def add(self, **kw) -> Participant:
        obj = Participant(**kw)
        self.s.add(obj)
        return obj

    def get(self, participant_id: str) -> Participant | None:
        return self.s.get(Participant, participant_id)

    def list(self, status: str | None = None) -> list[Participant]:
        q = select(Participant).order_by(Participant.participant_id)
        if status:
            q = q.where(Participant.status == status)
        return list(self.s.scalars(q))

    def set_status(self, participant_id: str, status: str, **kw) -> Participant:
        obj = self.get(participant_id)
        obj.status = status
        for k, v in kw.items():
            setattr(obj, k, v)
        return obj


class ViewRepository:
    def __init__(self, session):
        self.s = session

    def add(self, **kw) -> View:
        obj = View(**kw)
        self.s.add(obj)
        return obj

    def active_for(self, participant_id: str) -> list[View]:
        q = select(View).where(View.participant_id == participant_id,
                               View.status.in_(["new", "hold"]),
                               View.end_at.is_(None)).order_by(View.submitted_at)
        return list(self.s.scalars(q))

    def close(self, view_id: str, end_at) -> View:
        obj = self.s.get(View, view_id)
        obj.status = "closed"
        obj.end_at = end_at
        return obj


class AccountRepository:
    def __init__(self, session):
        self.s = session

    def add(self, **kw) -> Account:
        obj = Account(**kw)
        self.s.add(obj)
        return obj

    def get(self, account_id: str) -> Account | None:
        return self.s.get(Account, account_id)

    def list(self, account_type: str | None = None) -> list[Account]:
        q = select(Account).order_by(Account.account_id)
        if account_type:
            q = q.where(Account.account_type == account_type)
        return list(self.s.scalars(q))


class EventRepository:
    """Append-only: no update/delete methods by design."""

    def __init__(self, session):
        self.s = session

    def append(self, **kw) -> Event:
        obj = Event(**kw)
        self.s.add(obj)
        return obj

    def list(self, event_type: str | None = None, limit: int = 1000) -> list[Event]:
        q = select(Event).order_by(Event.timestamp)
        if event_type:
            q = q.where(Event.event_type == event_type)
        return list(self.s.scalars(q.limit(limit)))


class NavRepository:
    """Append-only: no update/delete methods by design."""

    def __init__(self, session):
        self.s = session

    def record(self, **kw) -> NavDaily:
        obj = NavDaily(**kw)
        self.s.add(obj)
        return obj

    def series(self, account_id: str) -> list[NavDaily]:
        q = select(NavDaily).where(NavDaily.account_id == account_id).order_by(NavDaily.date)
        return list(self.s.scalars(q))


class OrderRepository:
    def __init__(self, session):
        self.s = session

    def add(self, **kw) -> Order:
        obj = Order(**kw)
        self.s.add(obj)
        return obj

    def pending(self, account_id: str | None = None) -> list[Order]:
        q = select(Order).where(Order.status == "pending").order_by(Order.effective_at)
        if account_id:
            q = q.where(Order.account_id == account_id)
        return list(self.s.scalars(q))

    def mark(self, order_id: str, status: str) -> Order:
        obj = self.s.get(Order, order_id)
        obj.status = status
        return obj


class TradeRepository:
    """Append-only: no update/delete methods by design."""

    def __init__(self, session):
        self.s = session

    def record(self, **kw) -> Trade:
        obj = Trade(**kw)
        self.s.add(obj)
        return obj

    def for_account(self, account_id: str) -> list[Trade]:
        q = select(Trade).where(Trade.account_id == account_id).order_by(Trade.execution_at)
        return list(self.s.scalars(q))


class UserRepository:
    def __init__(self, session):
        self.s = session

    def add(self, **kw):
        from ..models.user import User
        obj = User(**kw)
        self.s.add(obj)
        return obj

    def get(self, user_id: str):
        from ..models.user import User
        return self.s.get(User, user_id)

    def by_email_normalized(self, email_normalized: str):
        from ..models.user import User
        return self.s.scalars(select(User).where(
            User.email_normalized == email_normalized)).first()

    def by_participant(self, participant_id: str):
        from ..models.user import User
        return self.s.scalars(select(User).where(
            User.participant_id == participant_id)).first()

    def list(self, limit: int = 50, offset: int = 0):
        from ..models.user import User
        q = select(User).order_by(User.user_id)
        return list(self.s.scalars(q.offset(offset).limit(limit))), \
            self.s.scalar(select(func.count()).select_from(User))


class SessionRepository:
    """Sessions are revoked, never deleted."""

    def __init__(self, session):
        self.s = session

    def add(self, **kw):
        from ..models.session import Session
        obj = Session(**kw)
        self.s.add(obj)
        return obj

    def by_token_hash(self, token_hash: str):
        from ..models.session import Session
        return self.s.scalars(select(Session).where(
            Session.token_hash == token_hash)).first()

    def active_for(self, user_id: str):
        from ..models.session import Session
        return list(self.s.scalars(select(Session).where(
            Session.user_id == user_id, Session.revoked_at.is_(None))
            .order_by(Session.created_at.desc())))


class ThemeRepository:
    def __init__(self, session):
        self.s = session

    def list(self, active: bool | None = True) -> list[Theme]:
        q = select(Theme).order_by(Theme.theme_id)
        if active is not None:
            q = q.where(Theme.active.is_(active))
        return list(self.s.scalars(q))

    def get(self, theme_id: str) -> Theme | None:
        return self.s.get(Theme, theme_id)


class TargetRepository:
    def __init__(self, session):
        self.s = session

    def record(self, **kw) -> PortfolioTarget:
        obj = PortfolioTarget(**kw)
        self.s.add(obj)
        return obj

    def latest(self, account_id: str, effective_le=None) -> PortfolioTarget | None:
        q = select(PortfolioTarget).where(PortfolioTarget.account_id == account_id)
        if effective_le is not None:
            q = q.where(PortfolioTarget.effective_date <= effective_le)
        return self.s.scalars(q.order_by(PortfolioTarget.effective_date.desc())).first()


class PriceRepository:
    def __init__(self, session):
        self.s = session

    def dates(self) -> list:
        return list(self.s.scalars(
            select(PriceDaily.date).distinct().order_by(PriceDaily.date)))

    def series(self, asset_id: str, end=None) -> list[tuple]:
        q = select(PriceDaily.date, PriceDaily.price).where(
            PriceDaily.asset_id == asset_id)
        if end is not None:
            q = q.where(PriceDaily.date <= end)
        return list(self.s.execute(q.order_by(PriceDaily.date)))
