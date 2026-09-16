"""Synchronous engine/session factory (SQLAlchemy 2.x style)."""
from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from . import models  # noqa: F401  (register all mappings)
from .base import Base
from .config import get_backend, get_database_url


@event.listens_for(Engine, "connect")
def _sqlite_fk_pragma(dbapi_connection, connection_record):
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    except Exception:
        pass


def pool_kwargs_for(url: str) -> dict:
    """Small, serverless-friendly pool for PostgreSQL; plain sqlite otherwise."""
    if url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {"pool_size": 3, "max_overflow": 2, "pool_timeout": 30,
            "pool_recycle": 300, "pool_pre_ping": True}


def create_app_engine(url: str | None = None, backend: str | None = None):
    backend = backend or get_backend()
    url = url or get_database_url(backend)
    return create_engine(url, future=True, **pool_kwargs_for(url))


def session_factory(engine=None):
    return sessionmaker(bind=engine or create_app_engine(), future=True)


def create_all(url: str | None = None) -> None:
    Base.metadata.create_all(create_app_engine(url))
