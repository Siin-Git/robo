"""Per-request DB session dependency (rollback on error, always closed)."""
from __future__ import annotations

from collections.abc import Iterator

from ..db.session import session_factory

_session_factory = None


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = session_factory()
    return _session_factory


def reset_session_factory() -> None:
    global _session_factory
    _session_factory = None


def get_db() -> Iterator:
    factory = get_session_factory()
    session = factory()
    try:
        from ..local.capstone import enabled
        if enabled() and session.get_bind().dialect.name == "sqlite":
            connection = session.connection()
            # The free hosted instance can spend several seconds serving a
            # comparison. Keep enrollment serialized, but let concurrent tabs
            # wait past SQLite's default five seconds instead of failing.
            connection.exec_driver_sql("PRAGMA busy_timeout=30000")
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
