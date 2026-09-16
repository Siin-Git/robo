"""Trade model (append-only: repository exposes no update/delete)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, DateCol

if TYPE_CHECKING:
    from .account import Account
    from .order import Order


class Trade(Base):
    __tablename__ = "trades"
    __table_args__ = (
        Index("ix_trades_account_execution", "account_id", "execution_at"),
    )

    trade_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    order_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("orders.order_id", ondelete="RESTRICT"), nullable=False)
    account_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("accounts.account_id", ondelete="RESTRICT"), nullable=False)
    asset_id: Mapped[str] = mapped_column(String(64), nullable=False)
    execution_at: Mapped[object] = mapped_column(DateCol, nullable=False)
    execution_price: Mapped[object] = mapped_column(Numeric(24, 8), nullable=False)
    quantity: Mapped[object] = mapped_column(Numeric(28, 10), nullable=False)
    gross_value: Mapped[object] = mapped_column(Numeric(24, 4), nullable=False)
    transaction_cost: Mapped[object] = mapped_column(Numeric(24, 8), nullable=False)
    net_value: Mapped[object] = mapped_column(Numeric(24, 4), nullable=False)

    order: Mapped["Order"] = relationship(back_populates="trades")
    account: Mapped["Account"] = relationship(back_populates="trades")
