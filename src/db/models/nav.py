"""Daily NAV model (append-only, composite PK like source)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, DateCol

if TYPE_CHECKING:
    from .account import Account


class NavDaily(Base):
    __tablename__ = "nav_daily"
    __table_args__ = (
        CheckConstraint("nav_status IN ('OK','STALE_PRICE','NAV_INCOMPLETE')",
                        name="nav_status_value"),
        Index("ix_nav_account_date", "account_id", "date"),
    )

    account_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("accounts.account_id", ondelete="RESTRICT"),
        primary_key=True)
    date: Mapped[object] = mapped_column(DateCol, primary_key=True)
    nav: Mapped[object] = mapped_column(Numeric(24, 8), nullable=False)
    nav_base100: Mapped[object] = mapped_column(Numeric(24, 8), nullable=False)
    daily_return: Mapped[object] = mapped_column(Numeric(18, 12), nullable=True)
    cumulative_return: Mapped[object] = mapped_column(Numeric(18, 12), nullable=False)
    cash_balance: Mapped[object] = mapped_column(Numeric(24, 4), nullable=False)
    stale_price_flag: Mapped[bool] = mapped_column(Boolean, nullable=False)
    nav_status: Mapped[str] = mapped_column(String(16), nullable=False)
    benchmark_version: Mapped[str] = mapped_column(String(32), nullable=False)
    theme_universe_version: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    execution_rule_version: Mapped[str] = mapped_column(String(64), nullable=False)

    account: Mapped["Account"] = relationship(back_populates="nav_rows")
