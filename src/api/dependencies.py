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
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
