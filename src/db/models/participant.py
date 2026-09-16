"""Participant model."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, DateCol, TZDateTime

if TYPE_CHECKING:
    from .account import Account
    from .event import Event
    from .view import View


class Participant(Base):
    __tablename__ = "participants"
    __table_args__ = (
        CheckConstraint("status IN ('active','inactive')", name="status_value"),
        Index("ix_participants_status", "status"),
    )

    participant_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    join_date: Mapped[object] = mapped_column(DateCol, nullable=False)
    leave_date: Mapped[object] = mapped_column(DateCol, nullable=True)
    created_at: Mapped[object] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[object] = mapped_column(TZDateTime, nullable=False)

    accounts: Mapped[list["Account"]] = relationship(back_populates="participant")
    views: Mapped[list["View"]] = relationship(back_populates="participant")
    events: Mapped[list["Event"]] = relationship(back_populates="participant_ref")
