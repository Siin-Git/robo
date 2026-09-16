"""Scheduled job registry model (idempotency + locking, additive)."""
from __future__ import annotations

from sqlalchemy import CheckConstraint, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import JSONBType, Base, DateCol, TZDateTime


class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"
    __table_args__ = (
        CheckConstraint("status IN ('running','success','failed','skipped')",
                        name="status_value"),
        Index("ix_jobs_type_scheduled", "job_type", "scheduled_for"),
        Index("ix_jobs_status", "status"),
    )

    job_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    job_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scheduled_for: Mapped[object] = mapped_column(DateCol, nullable=False)
    started_at: Mapped[object] = mapped_column(TZDateTime, nullable=True)
    completed_at: Mapped[object] = mapped_column(TZDateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    error_message: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    github_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stats_json: Mapped[dict] = mapped_column(JSONBType, nullable=False, default=dict)
