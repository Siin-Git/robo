"""Shared SQLAlchemy base + backend-portable column types.

Primary target is PostgreSQL (TIMESTAMPTZ / JSONB / NUMERIC). Variants keep
the same models executable on SQLite for tests and offline verification.
"""
from __future__ import annotations

from sqlalchemy import JSON, TIMESTAMP, Date, DateTime, MetaData
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase

convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=convention)


# TIMESTAMPTZ on PostgreSQL, timezone-aware DATETIME on SQLite.
TZDateTime = TIMESTAMP(timezone=True).with_variant(DateTime(timezone=True), "sqlite")

# JSONB on PostgreSQL, plain JSON on SQLite (semantic parity in scripts).
JSONBType = JSONB().with_variant(JSON(), "sqlite")

# Bare calendar days on both backends.
DateCol = Date()
