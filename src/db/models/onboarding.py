"""Onboarding draft model (one active draft per user, reload-persistent)."""
from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, JSONBType, TZDateTime


class OnboardingDraft(Base):
    __tablename__ = "onboarding_drafts"

    user_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    participant_id: Mapped[str] = mapped_column(String(16), nullable=False)
    frontier_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    frontier_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    theme_ids_json: Mapped[dict] = mapped_column(JSONBType, nullable=False, default=list)
    reason: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    current_step: Mapped[str] = mapped_column(String(16), nullable=False, default="risk")
    rebalance_frequency: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[object] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[object] = mapped_column(TZDateTime, nullable=False)
    completed_at: Mapped[object] = mapped_column(TZDateTime, nullable=True)
