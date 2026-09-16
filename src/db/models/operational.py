"""Operational tables: ID counters + lifecycle state (migrated as-is)."""
from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, TZDateTime


class Counter(Base):
    __tablename__ = "counters"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[int] = mapped_column(Integer, nullable=False)


class ForwardState(Base):
    __tablename__ = "forward_state"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str | None] = mapped_column(String(256), nullable=True)
    updated_at: Mapped[object] = mapped_column(TZDateTime, nullable=True)
