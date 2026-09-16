"""Daily price store model."""
from __future__ import annotations

from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, DateCol


class PriceDaily(Base):
    __tablename__ = "prices_daily"

    asset_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    date: Mapped[object] = mapped_column(DateCol, primary_key=True)
    price: Mapped[object] = mapped_column(Numeric(24, 8), nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
