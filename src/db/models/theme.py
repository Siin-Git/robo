"""Theme registry model (ticker inline; versioned via valid_from/valid_to)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, DateCol

if TYPE_CHECKING:
    from .view import View


class Theme(Base):
    __tablename__ = "themes"
    __table_args__ = (
        CheckConstraint("theme_type IN ('sector','subsector','theme')",
                        name="theme_type_value"),
    )

    theme_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    theme_type: Mapped[str] = mapped_column(String(16), nullable=False)
    ticker: Mapped[str | None] = mapped_column(String(16), nullable=True)
    market: Mapped[str | None] = mapped_column(String(16), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    valid_from: Mapped[object] = mapped_column(DateCol, nullable=True)
    valid_to: Mapped[object] = mapped_column(DateCol, nullable=True)
    universe_version: Mapped[str] = mapped_column(String(32), nullable=False)
    inactive_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)

    views: Mapped[list["View"]] = relationship(back_populates="theme")
