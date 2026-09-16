"""Immutable audit event model (append-only: no update/delete API)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, JSONBType, TZDateTime

if TYPE_CHECKING:
    from .account import Account
    from .participant import Participant


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_timestamp", "timestamp"),
        Index("ix_events_type", "event_type"),
        Index("ix_events_participant", "participant_id"),
        Index("ix_events_account", "account_id"),
    )

    event_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    participant_id: Mapped[str | None] = mapped_column(
        String(16), ForeignKey("participants.participant_id", ondelete="RESTRICT"),
        nullable=True)
    account_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("accounts.account_id", ondelete="RESTRICT"), nullable=True)
    timestamp: Mapped[object] = mapped_column("timestamp", TZDateTime, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONBType, nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)

    participant_ref: Mapped["Participant | None"] = relationship(back_populates="events")
    account_ref: Mapped["Account | None"] = relationship(back_populates="events")
