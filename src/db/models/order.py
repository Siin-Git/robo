"""Order model."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, DateCol, TZDateTime

if TYPE_CHECKING:
    from .account import Account
    from .trade import Trade


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("side IN ('buy','sell')", name="side_value"),
        CheckConstraint("status IN ('pending','executed','cancelled')", name="status_value"),
        Index("ix_orders_account_status", "account_id", "status"),
        Index("ix_orders_effective", "effective_at"),
    )

    order_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("accounts.account_id", ondelete="RESTRICT"), nullable=False)
    asset_id: Mapped[str] = mapped_column(String(64), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    target_weight: Mapped[object] = mapped_column(Numeric(18, 12), nullable=False)
    submitted_at: Mapped[object] = mapped_column(TZDateTime, nullable=False)
    effective_at: Mapped[object] = mapped_column(DateCol, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[object] = mapped_column(TZDateTime, nullable=False)

    account: Mapped["Account"] = relationship(back_populates="orders")
    trades: Mapped[list["Trade"]] = relationship(back_populates="order")
