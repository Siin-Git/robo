"""Synchronous engine/session factory (SQLAlchemy 2.x style)."""
from __future__ import annotations

import sqlite3  

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from . import models  # noqa: F401  (register all mappings)
from .base import Base
from .config import get_backend, get_database_url


@event.listens_for(Engine, "connect")
def _sqlite_fk_pragma(dbapi_connection, connection_record):
    # PRAGMA 는 SQLite 전용이다. PostgreSQL 연결에 보내면 문법 오류가 나고,
    # 그 연결의 트랜잭션이 중단 상태(InFailedSqlTransaction)가 되어 이후 모든
    # 쿼리가 실패한다. 반드시 SQLite 연결에만 실행한다.
    if not isinstance(dbapi_connection, sqlite3.Connection):
        return
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


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
