"""User base portfolio selection on Efficient Frontier (additive, no overwrite)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, JSONBType, TZDateTime

if TYPE_CHECKING:
    from .participant import Participant
    from .user import User


class BasePortfolioSelection(Base):
    __tablename__ = "base_portfolio_selections"
    __table_args__ = (
        CheckConstraint("status IN ('active','superseded')", name="status_value"),
        Index("ix_base_sel_user", "user_id"),
        Index("ix_base_sel_participant", "participant_id"),
        Index("ix_base_sel_frontier", "frontier_version", "frontier_id"),
    )

    selection_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False)
    participant_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("participants.participant_id", ondelete="RESTRICT"),
        nullable=False)
    frontier_version: Mapped[str] = mapped_column(String(32), nullable=False)
    frontier_id: Mapped[str] = mapped_column(String(16), nullable=False)
    expected_return: Mapped[object] = mapped_column(__import__("sqlalchemy").Numeric(18, 12), nullable=False)
    volatility: Mapped[object] = mapped_column(__import__("sqlalchemy").Numeric(18, 12), nullable=False)
    sharpe: Mapped[object] = mapped_column(__import__("sqlalchemy").Numeric(18, 12), nullable=True)
    weights_json: Mapped[dict] = mapped_column(JSONBType, nullable=False)
    selected_at: Mapped[object] = mapped_column(TZDateTime, nullable=False)
    effective_at: Mapped[object] = mapped_column(TZDateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")

    user: Mapped["User"] = relationship()
    participant: Mapped["Participant"] = relationship()
