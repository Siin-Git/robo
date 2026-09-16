"""Weekly view model."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, DateCol, TZDateTime

if TYPE_CHECKING:
    from .participant import Participant
    from .theme import Theme


class View(Base):
    __tablename__ = "views"
    __table_args__ = (
        CheckConstraint("status IN ('new','hold','closed','rejected')", name="status_value"),
        Index("ix_views_participant_effective", "participant_id", "effective_at"),
        Index("ix_views_status", "status"),
        Index("ix_views_theme", "theme_id"),
    )

    view_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    participant_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("participants.participant_id", ondelete="RESTRICT"),
        nullable=False)
    theme_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("themes.theme_id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    submitted_at: Mapped[object] = mapped_column(TZDateTime, nullable=False)
    effective_at: Mapped[object] = mapped_column(DateCol, nullable=False)
    end_at: Mapped[object] = mapped_column(TZDateTime, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    theme_universe_version: Mapped[str] = mapped_column(String(32), nullable=False)
    cycle_week: Mapped[str] = mapped_column(DateCol, nullable=False)
    cycle_date: Mapped[object] = mapped_column(DateCol, nullable=True)

    participant: Mapped["Participant"] = relationship(back_populates="views")
    theme: Mapped["Theme"] = relationship(back_populates="views")
