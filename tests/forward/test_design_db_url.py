"""설계 DB 주소를 URL 로 정한다 (PostgreSQL 배포 준비).

캡스톤 모드에서는 DB 가 둘이다.

- 인증·비교 시연 DB : ``get_database_url()``
- 설계·운용 기록 DB : ``get_design_database_url()``

예전에는 "인증 DB 파일 **옆의** portfolio_design.db" 라는 경로 규칙으로 갈랐다.
SQLite 는 경로가 곧 주소라 충분했지만 PostgreSQL 은 파일이 아니다. 그래서
``connect()`` 의 postgres 갈래는 ``DATABASE_URL`` 하나만 보고 있었고, 그대로
배포하면 **운용 기록이 인증·시연 DB 에 섞여 들어간다.** 조용히 일어나는 사고라
여기서 못을 박는다.

기본값은 바꾸지 않는다. 환경변수가 없으면 예전 파일 규칙 그대로다.
"""
from __future__ import annotations

import os
from contextlib import contextmanager

import pytest


@contextmanager
def envs(**kv):
    """테스트 사이에 환경변수가 새지 않도록 복원한다."""
    old = {k: os.environ.get(k) for k in kv}
    try:
        for k, v in kv.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        yield
    finally:
        for k, v in old.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


CAPSTONE = dict(CAPSTONE_DEMO="1", APP_PROFILE="local")
# Neon 콘솔에서 복사하면 이 형태다(드라이버 없음).
PG = "postgresql://u:secret@host.neon.tech/robo_design"
# 코드가 쓰는 형태. psycopg3 을 명시한다(normalize_pg_url).
PG_DRIVER = "postgresql+psycopg://u:secret@host.neon.tech/robo_design"


# --------------------------------------------------------------------------
# 어느 DB 를 가리키는가
# --------------------------------------------------------------------------

def test_캡스톤_모드가_아니면_설계_DB가_없다():
    from src.db.config import get_design_database_url
    with envs(CAPSTONE_DEMO=None, APP_PROFILE="live", DATABASE_BACKEND="sqlite",
              CAPSTONE_DESIGN_DATABASE_URL=None):
        assert get_design_database_url() is None


def test_프로파일이_local이_아니면_설계_DB가_없다():
    """CAPSTONE_DEMO 만 켜도 live 프로파일에서는 적용되지 않는다."""
    from src.db.config import get_design_database_url
    with envs(CAPSTONE_DEMO="1", APP_PROFILE="live", DATABASE_BACKEND="sqlite",
              CAPSTONE_DESIGN_DATABASE_URL=None):
        assert get_design_database_url() is None


def test_sqlite면_예전_파일_규칙_그대로다(tmp_path):
    from src.db.config import get_design_database_url
    with envs(**CAPSTONE, DATABASE_BACKEND="sqlite",
              CAPSTONE_DATA_DIR=str(tmp_path), CAPSTONE_DESIGN_DATABASE_URL=None):
        url = get_design_database_url()
    assert url == f"sqlite:///{tmp_path / 'portfolio_design.db'}"


def test_명시된_URL이_있으면_그것을_쓴다(tmp_path):
    from src.db.config import get_design_database_url
    with envs(**CAPSTONE, DATABASE_BACKEND="sqlite",
              CAPSTONE_DATA_DIR=str(tmp_path), CAPSTONE_DESIGN_DATABASE_URL=PG):
        assert get_design_database_url() == PG_DRIVER


def test_postgres인데_설계_URL이_없으면_거부한다():
    """추측해서 고르면 운용 기록이 인증 DB 로 조용히 섞인다."""
    from src.db.config import get_design_database_url
    with envs(**CAPSTONE, DATABASE_BACKEND="postgres",
              DATABASE_URL="postgresql://u:p@h/auth", CAPSTONE_DESIGN_DATABASE_URL=None):
        with pytest.raises(ValueError) as e:
            get_design_database_url()
    assert "CAPSTONE_DESIGN_DATABASE_URL" in str(e.value)


def test_postgres에서_설계_URL을_돌려준다():
    from src.db.config import get_design_database_url
    with envs(**CAPSTONE, DATABASE_BACKEND="postgres",
              DATABASE_URL="postgresql://u:p@h/auth", CAPSTONE_DESIGN_DATABASE_URL=PG):
        assert get_design_database_url() == PG_DRIVER


def test_인증_DB와_설계_DB가_서로_다르다():
    """둘이 같으면 시연 데이터와 운용 기록이 한 테이블에 섞인다."""
    from src.db.config import get_database_url, get_design_database_url
    with envs(**CAPSTONE, DATABASE_BACKEND="postgres",
              DATABASE_URL="postgresql://u:p@h/robo_auth",
              CAPSTONE_DESIGN_DATABASE_URL=PG):
        assert get_database_url() != get_design_database_url()


# --------------------------------------------------------------------------
# 엔진이 실제로 그 주소로 연결하는가 (이 버그의 핵심)
# --------------------------------------------------------------------------

def test_connect가_postgres에서_설계_DB로_간다(monkeypatch, tmp_path):
    from src.forward import db as fdb, pg_adapter
    seen = {}
    monkeypatch.setattr(pg_adapter, "connect_postgres",
                        lambda url: seen.setdefault("url", url))
    with envs(**CAPSTONE, DATABASE_BACKEND="postgres",
              DATABASE_URL="postgresql://u:p@h/robo_auth",
              CAPSTONE_DESIGN_DATABASE_URL=PG):
        fdb.connect(tmp_path / "ignored.db")
    assert seen["url"] == PG_DRIVER, "엔진이 인증 DB 에 기록하려 하고 있다"


def test_캡스톤이_아니면_예전처럼_DATABASE_URL을_쓴다(monkeypatch, tmp_path):
    from src.forward import db as fdb, pg_adapter
    seen = {}
    monkeypatch.setattr(pg_adapter, "connect_postgres",
                        lambda url: seen.setdefault("url", url))
    with envs(CAPSTONE_DEMO=None, APP_PROFILE="live", DATABASE_BACKEND="postgres",
              DATABASE_URL="postgresql://u:p@h/robo_live",
              CAPSTONE_DESIGN_DATABASE_URL=None):
        fdb.connect(tmp_path / "ignored.db")
    assert seen["url"] == "postgresql://u:p@h/robo_live"


def test_sqlite는_아무것도_바뀌지_않는다(tmp_path):
    """기본 경로는 건드리지 않는다. 금요일 운영이 여기에 걸려 있다."""
    from src.forward.db import connect
    from src.forward.runtime import get_database_path
    with envs(**CAPSTONE, DATABASE_BACKEND="sqlite",
              CAPSTONE_DATA_DIR=str(tmp_path), CAPSTONE_DESIGN_DATABASE_URL=None):
        assert get_database_path() == tmp_path / "portfolio_design.db"
        con = connect(get_database_path())
        try:
            assert con.execute("SELECT 1").fetchone()[0] == 1
        finally:
            con.close()


# --------------------------------------------------------------------------
# 배너
# --------------------------------------------------------------------------

def test_배너가_설계_DB를_가리킨다():
    from src.forward.runtime import safety_banner
    with envs(**CAPSTONE, DATABASE_BACKEND="postgres",
              DATABASE_URL="postgresql://u:p@h/robo_auth",
              CAPSTONE_DESIGN_DATABASE_URL=PG):
        banner = safety_banner()
    assert "MODE: CAPSTONE" in banner
    assert "BACKEND: POSTGRES" in banner
    assert "robo_design" in banner, "어느 DB 에 기록되는지 배너로 알 수 없다"


def test_배너가_비밀번호를_노출하지_않는다():
    from src.forward.runtime import safety_banner
    with envs(**CAPSTONE, DATABASE_BACKEND="postgres",
              DATABASE_URL="postgresql://u:p@h/robo_auth",
              CAPSTONE_DESIGN_DATABASE_URL=PG):
        banner = safety_banner()
    assert "secret" not in banner


def test_설정이_빠졌을때_배너가_멈추지_않는다():
    """배너는 진단 도구다. 설정 오류로 죽으면 원인을 볼 수 없다."""
    from src.forward.runtime import safety_banner
    with envs(**CAPSTONE, DATABASE_BACKEND="postgres",
              DATABASE_URL="postgresql://u:p@h/robo_auth",
              CAPSTONE_DESIGN_DATABASE_URL=None):
        banner = safety_banner()
    assert "CAPSTONE_DESIGN_DATABASE_URL" in banner


# --------------------------------------------------------------------------
# API 쪽: 인증 세션에서 파생하는 기본값을 지킨다
# --------------------------------------------------------------------------

def _auth_session(path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    return Session(create_engine(f"sqlite:///{path}"))


def test_API는_기본적으로_인증_DB_옆_파일을_쓴다(tmp_path):
    """환경변수가 아니라 요청이 실제로 쓰는 DB 를 따라간다.

    테스트는 임시 DB 로 도는데 CAPSTONE_DATA_DIR 은 보통 설정하지 않는다.
    환경변수를 먼저 보면 개발자의 진짜 운용 DB 를 열게 된다.
    """
    from src.api.design_workspace import design_database_url
    auth = tmp_path / "capstone_demo.db"
    session = _auth_session(auth)
    try:
        with envs(CAPSTONE_DESIGN_DATABASE_URL=None):
            url = design_database_url(session)
    finally:
        session.close()
    assert url == f"sqlite:///{(tmp_path / 'portfolio_design.db').resolve()}"


def test_인증DB가_SQLite면_환경변수를_무시한다(tmp_path):
    """이게 없으면 테스트가 운영 DB 에 쓴다.

    개발자의 .env.local 에는 운영용 CAPSTONE_DESIGN_DATABASE_URL 이 들어 있다.
    테스트는 임시 SQLite 로 돌면서 CAPSTONE_DEMO 만 켠다. 환경변수를 먼저
    보면 그 순간 pytest 가 Neon 에 테이블을 만들고 데이터를 남긴다.
    """
    from src.api.design_workspace import design_database_url
    auth = tmp_path / "capstone_demo.db"
    session = _auth_session(auth)
    try:
        with envs(CAPSTONE_DESIGN_DATABASE_URL=PG):
            url = design_database_url(session)
    finally:
        session.close()
    assert url == f"sqlite:///{(tmp_path / 'portfolio_design.db').resolve()}"
    assert "neon" not in url


def test_팩토리는_경로가_아니라_URL을_받는다(tmp_path):
    """호출 규약이 경로에서 URL 로 바뀌었다.

    경로를 그대로 넘기면 SQLAlchemy 가 "Could not parse SQLAlchemy URL" 만
    남기고 죽는다. 어느 인자가 잘못됐는지 말해 주는 편이 낫다.
    """
    from src.api.design_workspace import _factory
    with pytest.raises(ValueError) as e:
        _factory(str(tmp_path / "portfolio_design.db"))
    assert "URL" in str(e.value)


def test_설계_DB가_인증_DB와_같으면_거부한다():
    """같으면 시연 데이터와 운용 기록이 한 테이블에 섞인다."""
    from src.api.design_workspace import design_database_url
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    same = "postgresql+psycopg://u:p@h.neon.tech/robo_auth"
    session = Session(create_engine(same))
    try:
        with envs(CAPSTONE_DESIGN_DATABASE_URL=same):
            with pytest.raises(RuntimeError):
                design_database_url(session)
    finally:
        session.close()


def test_인증DB가_PostgreSQL이면_설계_URL을_쓴다():
    from src.api.design_workspace import design_database_url
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    session = Session(create_engine("postgresql+psycopg://u:p@h.neon.tech/robo_auth"))
    try:
        with envs(CAPSTONE_DESIGN_DATABASE_URL=PG):
            assert design_database_url(session) == PG_DRIVER
    finally:
        session.close()


def test_인증DB가_PostgreSQL인데_설계_URL이_없으면_거부한다():
    from src.api.design_workspace import design_database_url
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    session = Session(create_engine("postgresql+psycopg://u:p@h.neon.tech/robo_auth"))
    try:
        with envs(CAPSTONE_DESIGN_DATABASE_URL=None):
            with pytest.raises(RuntimeError):
                design_database_url(session)
    finally:
        session.close()


# --------------------------------------------------------------------------
# 드라이버 (Neon 콘솔이 주는 문자열을 그대로 붙여넣어도 돌아야 한다)
# --------------------------------------------------------------------------

def test_psycopg3_드라이버를_명시한다():
    """SQLAlchemy 는 'postgresql://' 를 psycopg2 로 읽는다.

    requirements.txt 에는 psycopg3 만 있다. 그대로 두면 런타임에
    "No module named 'psycopg2'" 로 죽는다.
    """
    from src.db.config import normalize_pg_url
    assert normalize_pg_url("postgresql://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalize_pg_url("postgres://u:p@h/db") == "postgresql+psycopg://u:p@h/db"


def test_이미_명시된_드라이버는_건드리지_않는다():
    from src.db.config import normalize_pg_url
    for url in ("postgresql+psycopg://u:p@h/db", "sqlite:////tmp/x.db"):
        assert normalize_pg_url(url) == url


def test_설계_URL도_정규화된다():
    """Neon 콘솔에서 복사한 문자열을 그대로 환경변수에 넣는 경우."""
    from src.db.config import get_design_database_url
    raw = "postgresql://u:p@h.neon.tech/robo_design?sslmode=require"
    with envs(**CAPSTONE, DATABASE_BACKEND="postgres",
              DATABASE_URL="postgresql://u:p@h.neon.tech/robo_auth",
              CAPSTONE_DESIGN_DATABASE_URL=raw):
        assert get_design_database_url().startswith("postgresql+psycopg://")


def test_쿼리_문자열이_보존된다():
    """sslmode / channel_binding 이 떨어지면 Neon 연결이 거부된다."""
    from src.db.config import normalize_pg_url
    out = normalize_pg_url(
        "postgresql://u:p@h/db?sslmode=require&channel_binding=require")
    assert out.endswith("?sslmode=require&channel_binding=require")


def test_드라이버만_다른_같은_DB를_겹친_것으로_본다(tmp_path):
    """한쪽은 postgresql://, 다른 쪽은 postgresql+psycopg:// 일 수 있다.

    같은 데이터베이스인데 다르다고 판정하면 시연 데이터와 운용 기록이
    한 곳에 섞이는 걸 못 막는다.
    """
    from src.api.design_workspace import _identity
    a = "postgresql://u:p@h.neon.tech/robo_auth?sslmode=require"
    b = "postgresql+psycopg://other:q@h.neon.tech/robo_auth"
    assert _identity(a) == _identity(b)


def test_다른_데이터베이스는_다르게_본다():
    from src.api.design_workspace import _identity
    a = "postgresql+psycopg://u:p@h.neon.tech/robo_auth"
    b = "postgresql+psycopg://u:p@h.neon.tech/robo_design"
    assert _identity(a) != _identity(b)
