"""Daily holdings snapshot model (append-only, composite PK like source)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, DateCol

if TYPE_CHECKING:
    from .account import Account


class Holding(Base):
    __tablename__ = "holdings_daily"
    __table_args__ = (
        Index("ix_holdings_account_date", "account_id", "date"),
    )

    account_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("accounts.account_id", ondelete="RESTRICT"),
        primary_key=True)
    date: Mapped[object] = mapped_column(DateCol, primary_key=True)
    asset_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    quantity: Mapped[object] = mapped_column(Numeric(28, 10), nullable=False)
    price: Mapped[object] = mapped_column(Numeric(24, 8), nullable=False)
    market_value: Mapped[object] = mapped_column(Numeric(24, 4), nullable=False)
    weight: Mapped[object] = mapped_column(Numeric(18, 12), nullable=False)

    account: Mapped["Account"] = relationship(back_populates="holdings")
