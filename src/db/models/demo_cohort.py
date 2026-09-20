"""Additive demo-only cohort reservations; no existing account is reassigned."""
from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from ..base import Base, JSONBType, TZDateTime


class DemoCohort(Base):
    __tablename__ = "demo_cohorts"
    cohort_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    prepared_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[object] = mapped_column(TZDateTime, nullable=False)


class DemoSlot(Base):
    __tablename__ = "demo_slots"
    __table_args__ = (UniqueConstraint("cohort_id", "slot_number"),)
    slot_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    cohort_id: Mapped[str] = mapped_column(ForeignKey("demo_cohorts.cohort_id"), nullable=False)
    slot_number: Mapped[int] = mapped_column(Integer, nullable=False)
    invite_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email_normalized: Mapped[str] = mapped_column(String(320), nullable=False)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"), unique=True)
    draft_json: Mapped[dict] = mapped_column(JSONBType, nullable=False, default=dict)
    configuration_json: Mapped[dict | None] = mapped_column(JSONBType)
    report_json: Mapped[dict | None] = mapped_column(JSONBType)
    confirmed_at: Mapped[object | None] = mapped_column(TZDateTime)
    forward_started_at: Mapped[object | None] = mapped_column(TZDateTime)
