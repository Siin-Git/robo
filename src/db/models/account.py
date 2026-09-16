"""Account model."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, DateCol, TZDateTime

if TYPE_CHECKING:
    from .event import Event
    from .holding import Holding
    from .nav import NavDaily
    from .order import Order
    from .participant import Participant
    from .portfolio import PortfolioTarget
    from .trade import Trade


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint("account_type IN ('core','personal','shadow')",
                        name="account_type_value"),
        Index("ix_accounts_participant", "participant_id"),
        Index("ix_accounts_type", "account_type"),
    )

    account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    participant_id: Mapped[str | None] = mapped_column(
        String(16), ForeignKey("participants.participant_id", ondelete="RESTRICT"),
        nullable=True)
    account_type: Mapped[str] = mapped_column(String(16), nullable=False)
    shadow_name: Mapped[str | None] = mapped_column(String(32), nullable=True)
    benchmark_version: Mapped[str] = mapped_column(String(32), nullable=False)
    inception_date: Mapped[object] = mapped_column(DateCol, nullable=False)
    initial_capital_krw: Mapped[object] = mapped_column(Numeric(24, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[object] = mapped_column(TZDateTime, nullable=False)

    participant: Mapped["Participant | None"] = relationship(back_populates="accounts")
    orders: Mapped[list["Order"]] = relationship(back_populates="account")
    trades: Mapped[list["Trade"]] = relationship(back_populates="account")
    holdings: Mapped[list["Holding"]] = relationship(back_populates="account")
    nav_rows: Mapped[list["NavDaily"]] = relationship(back_populates="account")
    targets: Mapped[list["PortfolioTarget"]] = relationship(back_populates="account")
    events: Mapped[list["Event"]] = relationship(back_populates="account_ref")
