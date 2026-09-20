"""Editable portfolio workspace; authentication and fixed comparisons stay in get_db.

Only capstone mode uses a separate SQLite file. No demo selections, NAV, passwords
or sessions are copied. Normal profiles retain their existing database unchanged.
"""
from functools import lru_cache
from pathlib import Path
from threading import RLock

from fastapi import Depends
from sqlalchemy import select

from .authz import get_current_user, require_authenticated_csrf
from .dependencies import get_db
from .errors import ApiError
from .services import participant_service
from .services import _common as C
from ..db.base import Base
from ..db.models.theme import Theme
from ..db.models.user import User
from ..db.session import create_app_engine, session_factory
from ..local.capstone import enabled

_lock = RLock()


@lru_cache(maxsize=8)
def _factory(path: str):
    engine = create_app_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    return session_factory(engine)


def get_design_db(auth_db=Depends(get_db), user=Depends(get_current_user)):
    if not enabled():
        yield auth_db
        return
    if not user.participant_id:
        raise ApiError("NO_PARTICIPANT", "User has no linked participant.", 409)
    source = auth_db.get_bind().url.database
    if not source or source == ":memory:":
        raise RuntimeError("Capstone design workspace requires a file-backed database")
    path = Path(source).resolve().with_name("portfolio_design.db")
    if path == Path(source).resolve():
        raise RuntimeError("Design and comparison databases must be separate")
    # Serialize first-use initialization; normal request transactions remain separate.
    with _lock:
        factory = _factory(str(path))
        with factory() as db:
            from .design_prices import load_reference_prices
            load_reference_prices(db)
            if db.get(User, user.user_id) is None:
                for theme in auth_db.scalars(select(Theme)):
                    if db.get(Theme, theme.theme_id) is None:
                        db.add(Theme(**{col.name: getattr(theme, col.name)
                                        for col in Theme.__table__.columns}))
                participant_service.create(db, user.participant.display_name,
                                           participant_id=user.participant_id)
                now = C.now_utc()
                # Identity reference for existing foreign keys, never a login account.
                db.add(User(user_id=user.user_id, participant_id=user.participant_id,
                            email=user.email, email_normalized=user.email_normalized,
                            password_hash="!identity-reference-only", status="disabled",
                            role="user", created_at=now, updated_at=now))
            db.commit()
    with factory() as db:
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise


def require_design_csrf(user=Depends(require_authenticated_csrf), db=Depends(get_design_db)):
    """Original session/CSRF validation, with writes confined to the design store."""
    return user
