"""Server-side session model (only token/CSRF hashes stored, never raw)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, TZDateTime

if TYPE_CHECKING:
    from .user import User


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_sessions_user", "user_id"),
        Index("ix_sessions_expires", "expires_at"),
        Index("ix_sessions_revoked", "revoked_at"),
    )

    session_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    csrf_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[object] = mapped_column(TZDateTime, nullable=False)
    expires_at: Mapped[object] = mapped_column(TZDateTime, nullable=False)
    last_seen_at: Mapped[object] = mapped_column(TZDateTime, nullable=True)
    revoked_at: Mapped[object] = mapped_column(TZDateTime, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    user: Mapped["User"] = relationship(back_populates="sessions")
