"""Daily performance metrics model."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, DateCol, JSONBType

if TYPE_CHECKING:
    from .account import Account


class PerformanceDaily(Base):
    __tablename__ = "performance_daily"

    account_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("accounts.account_id", ondelete="RESTRICT"),
        primary_key=True)
    date: Mapped[object] = mapped_column(DateCol, primary_key=True)
    metrics_json: Mapped[dict] = mapped_column(JSONBType, nullable=False)

    account: Mapped["Account"] = relationship()
