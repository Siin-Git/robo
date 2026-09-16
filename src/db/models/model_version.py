"""Model version registry model."""
from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, JSONBType, TZDateTime


class ModelVersion(Base):
    __tablename__ = "model_versions"

    version_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version_type: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[object] = mapped_column(TZDateTime, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONBType, nullable=False)
