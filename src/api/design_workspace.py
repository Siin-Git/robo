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


def _apply_portfolio_reset(db, auth_db, user):
    """Apply the committed reset once, without deleting prior designs or trades."""
    from .services.enrollment_service import latest_reset
    from ..db.models.operational import ForwardState
    from ..db.models.base_selection import BasePortfolioSelection
    from ..db.models.onboarding import OnboardingDraft
    from ..db.models.view import View
    reset = latest_reset(auth_db, user.participant_id)
    if reset is None:
        return
    key = f"portfolio_reset:{user.user_id}"
    receipt = db.get(ForwardState, key)
    if receipt and receipt.value == reset.event_id:
        return
    for selection in db.scalars(select(BasePortfolioSelection).where(
            BasePortfolioSelection.user_id == user.user_id, BasePortfolioSelection.status == "active")):
        selection.status = "superseded"
    for view in db.scalars(select(View).where(View.participant_id == user.participant_id,
            View.end_at.is_(None), View.status.in_(["new", "hold"]))):
        view.status = "closed"
        view.end_at = reset.timestamp
    draft = db.get(OnboardingDraft, user.user_id)
    if draft:
        C.log_event(db, "ONBOARDING_RESET", "CORE_V0.3", participant_id=user.participant_id,
            payload={"frontier_id": draft.frontier_id, "theme_ids": draft.theme_ids_json, "reason": draft.reason})
        draft.frontier_id = None
        draft.theme_ids_json = []
        draft.reason = ""
        draft.completed_at = reset.timestamp
        draft.updated_at = reset.timestamp
        draft.current_step = "reset"
    db.merge(ForwardState(key=key, value=reset.event_id, updated_at=reset.timestamp))


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
            _apply_portfolio_reset(db, auth_db, user)
            db.commit()
    with factory() as db:
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise


def require_design_csrf(user=Depends(require_authenticated_csrf), db=Depends(get_design_db), auth_db=Depends(get_db)):
    """Original session/CSRF validation, with writes confined to the design store."""
    from .services.enrollment_service import own
    slot = own(auth_db, user)
    if slot and not slot.confirmed_at:
        raise ApiError("SETUP_REQUIRED", "먼저 공통 CORE와 Theme의 첫 설정을 완료해 주세요.", 409)
    return user
