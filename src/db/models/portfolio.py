"""Portfolio target (header + JSON weights) model."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, DateCol, JSONBType, TZDateTime

if TYPE_CHECKING:
    from .account import Account


class PortfolioTarget(Base):
    __tablename__ = "portfolio_targets"
    __table_args__ = (
        Index("ix_targets_account_effective", "account_id", "effective_date"),
    )

    target_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("accounts.account_id", ondelete="RESTRICT"), nullable=False)
    effective_date: Mapped[object] = mapped_column(DateCol, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    weights_json: Mapped[dict] = mapped_column(JSONBType, nullable=False)
    core_version: Mapped[str] = mapped_column(String(32), nullable=False)
    theme_universe_version: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[object] = mapped_column(TZDateTime, nullable=False)

    account: Mapped["Account"] = relationship(back_populates="targets")
