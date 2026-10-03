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
def _factory(url: str):
    """설계 DB 세션 팩토리. 인자는 **DB URL** 이다(파일 경로가 아니다).

    예전에는 경로를 받아 안에서 ``sqlite:///`` 를 붙였다. PostgreSQL 을
    지원하면서 URL 로 바꿨는데, 경로를 그대로 넘기면 SQLAlchemy 가
    "Could not parse SQLAlchemy URL" 만 남기고 죽어 원인을 찾기 어렵다.
    """
    if "://" not in url:
        raise ValueError(
            f"_factory 는 DB URL 을 받는다(경로가 아니다): {url!r}. "
            f"파일이면 'sqlite:///<경로>' 형태로 넘길 것.")
    engine = create_app_engine(url)
    from ..db.design_schema import ensure_design_schema
    ensure_design_schema(engine)
    return session_factory(engine)


def _identity(url) -> tuple:
    """두 DB 가 같은 곳인지 비교할 때 쓰는 값. 비밀번호는 보지 않는다.

    드라이버(``+psycopg``)는 떼고 백엔드만 본다. 같은 데이터베이스를 한쪽은
    ``postgresql://``, 다른 쪽은 ``postgresql+psycopg://`` 로 가리킬 수 있는데,
    그 둘은 **같은 곳**이다. 드라이버까지 비교하면 겹치는데도 통과시킨다.
    """
    from sqlalchemy.engine import make_url
    u = make_url(str(url)) if not hasattr(url, "drivername") else url
    backend = u.drivername.split("+", 1)[0]
    database = u.database
    if backend == "sqlite" and database:
        database = str(Path(database).resolve())
    return (backend, u.host, u.port, database)


def design_database_url(auth_db) -> str:
    """설계 워크스페이스 DB 의 주소.

    **설계 DB 는 인증 DB 를 따라간다.** 둘은 짝이다.

    - 인증 DB 가 PostgreSQL 이면 ``CAPSTONE_DESIGN_DATABASE_URL`` 을 쓴다.
    - 인증 DB 가 SQLite 파일이면 그 **옆의** ``portfolio_design.db`` 를 쓴다.

    환경변수를 먼저 보지 않는 이유가 중요하다. 테스트는 임시 SQLite 파일로
    돌면서 CAPSTONE_DEMO 만 켠다. 개발자의 ``.env.local`` 에 운영용
    ``CAPSTONE_DESIGN_DATABASE_URL`` 이 들어 있으면, 환경변수를 먼저 보는
    순간 **테스트가 운영 DB 에 테이블을 만들고 데이터를 쓴다.** 요청이 실제로
    쓰고 있는 DB 를 따라가면 그런 일이 일어나지 않는다.
    """
    import os
    from ..db.config import normalize_pg_url
    auth_url = auth_db.get_bind().url
    auth_backend = auth_url.drivername.split("+", 1)[0]
    explicit = os.environ.get("CAPSTONE_DESIGN_DATABASE_URL", "").strip()
    if auth_backend != "sqlite":
        if not explicit:
            raise RuntimeError(
                "인증 DB 가 SQLite 파일이 아니면 설계 DB 를 경로로 찾을 수 없다. "
                "CAPSTONE_DESIGN_DATABASE_URL 을 설정할 것.")
        # Neon 콘솔이 주는 'postgresql://' 는 SQLAlchemy 가 psycopg2 로 읽는다.
        explicit = normalize_pg_url(explicit)
        if _identity(explicit) == _identity(auth_url):
            raise RuntimeError("Design and comparison databases must be separate")
        return explicit
    source = auth_db.get_bind().url.database
    if not source or source == ":memory:":
        raise RuntimeError(
            "Capstone design workspace requires a file-backed database, or an "
            "explicit CAPSTONE_DESIGN_DATABASE_URL.")
    path = Path(source).resolve().with_name("portfolio_design.db")
    if path == Path(source).resolve():
        raise RuntimeError("Design and comparison databases must be separate")
    return f"sqlite:///{path}"


def get_design_db(auth_db=Depends(get_db), user=Depends(get_current_user)):
    if not enabled():
        yield auth_db
        return
    if not user.participant_id:
        raise ApiError("NO_PARTICIPANT", "User has no linked participant.", 409)
    url = design_database_url(auth_db)
    # Serialize first-use initialization; normal request transactions remain separate.
    with _lock:
        factory = _factory(url)
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
