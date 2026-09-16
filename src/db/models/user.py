"""User account model (Phase 3C). One user links to at most one participant."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, TZDateTime

if TYPE_CHECKING:
    from .participant import Participant
    from .session import Session


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('user','admin')", name="role_value"),
        CheckConstraint("status IN ('active','disabled')", name="status_value"),
        Index("ix_users_status", "status"),
        Index("ix_users_role", "role"),
    )

    user_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    email_normalized: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="user")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    participant_id: Mapped[str | None] = mapped_column(
        String(16), ForeignKey("participants.participant_id", ondelete="RESTRICT"),
        nullable=True, unique=True)
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[object] = mapped_column(TZDateTime, nullable=True)
    created_at: Mapped[object] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[object] = mapped_column(TZDateTime, nullable=False)
    last_login_at: Mapped[object] = mapped_column(TZDateTime, nullable=True)
    password_changed_at: Mapped[object] = mapped_column(TZDateTime, nullable=True)

    participant: Mapped["Participant | None"] = relationship()
    sessions: Mapped[list["Session"]] = relationship(back_populates="user")
