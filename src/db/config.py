"""Database configuration: env-driven, no hardcoded paths or secrets."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        # Shared defaults may live in .env. Developer-specific local values live
        # in .env.local; both files are ignored by Git. Existing process
        # variables always win, so deployment settings cannot be overwritten by
        # a local file.
        load_dotenv(ROOT / ".env.local")
        load_dotenv(ROOT / ".env")
    except Exception:
        pass


_load_dotenv()

BACKENDS = ("sqlite", "postgres")


def get_backend() -> str:
    backend = os.environ.get("DATABASE_BACKEND", "sqlite").strip().lower()
    if backend not in BACKENDS:
        raise ValueError(f"unknown DATABASE_BACKEND={backend!r}")
    return backend


def normalize_pg_url(url: str) -> str:
    """PostgreSQL URL 에 psycopg3 드라이버를 명시한다.

    SQLAlchemy 는 ``postgresql://`` 를 **psycopg2** 로 해석한다. 이 프로젝트는
    ``psycopg>=3.1`` 만 설치하므로(requirements.txt) 그대로 두면 런타임에
    ``No module named 'psycopg2'`` 로 죽는다.

    Neon 콘솔이 주는 문자열이 정확히 ``postgresql://`` 형태라 그대로
    붙여넣기 쉽다. 사람이 매번 고치게 두는 대신 여기서 맞춘다.
    드라이버가 이미 명시돼 있으면 건드리지 않는다.
    """
    for bare, driver in (("postgresql://", "postgresql+psycopg://"),
                         ("postgres://", "postgresql+psycopg://")):
        if url.startswith(bare):
            return driver + url[len(bare):]
    return url


def get_database_url(backend: str | None = None) -> str:
    backend = backend or get_backend()
    if backend == "postgres":
        url = os.environ.get("DATABASE_URL", "").strip()
        if not url:
            raise ValueError("DATABASE_URL is not set (required for postgres backend)")
        return normalize_pg_url(url)
    # Local profile has its own file; APP_PROFILE=local takes precedence over SQLITE_PATH.
    if os.environ.get("APP_PROFILE", "").strip().lower() == "local":
        if os.environ.get("CAPSTONE_DEMO") == "1":
            demo_dir = Path(os.environ.get("CAPSTONE_DATA_DIR") or ROOT / "data")
            return f"sqlite:///{demo_dir / 'capstone_demo.db'}"
        return f"sqlite:///{ROOT / 'data' / 'forward_local.db'}"
    path = os.environ.get("SQLITE_PATH", str(ROOT / "data" / "forward_test.db"))
    return f"sqlite:///{path}"


def capstone_mode() -> bool:
    """캡스톤 모드(설계 워크스페이스를 따로 두는 모드)인지."""
    return (os.environ.get("CAPSTONE_DEMO") == "1"
            and os.environ.get("APP_PROFILE", "").strip().lower() == "local")


def get_design_database_url(backend: str | None = None) -> str | None:
    """설계 워크스페이스(=운용 기록)가 사는 DB 의 URL. 캡스톤 모드가 아니면 None.

    캡스톤 모드에서는 DB 가 둘이다.

    - 인증·비교 시연 DB : ``get_database_url()``
    - 설계·운용 기록 DB : 이 함수

    예전에는 "인증 DB 파일 옆의 portfolio_design.db" 라는 **경로 규칙**으로
    갈랐다. SQLite 는 경로가 곧 주소라 그것으로 충분했지만, PostgreSQL 은
    파일이 아니어서 규칙 자체가 성립하지 않았다. 그래서 주소를 URL 로 정한다.

    - ``CAPSTONE_DESIGN_DATABASE_URL`` 이 있으면 그것을 쓴다(백엔드 무관).
    - 없고 SQLite 면 예전 파일 규칙을 그대로 쓴다(로컬 개발은 안 바뀐다).
    - 없고 PostgreSQL 이면 **거부한다.** 추측해서 고르면 운용 기록이 인증 DB
      에 섞이거나 빈 DB 에 쌓이는데, 둘 다 조용히 일어나 뒤늦게 발견된다.
    """
    if not capstone_mode():
        return None
    url = os.environ.get("CAPSTONE_DESIGN_DATABASE_URL", "").strip()
    if url:
        return normalize_pg_url(url)
    backend = backend or get_backend()
    if backend == "postgres":
        raise ValueError(
            "캡스톤 모드에서 DATABASE_BACKEND=postgres 면 "
            "CAPSTONE_DESIGN_DATABASE_URL 을 반드시 설정해야 한다. "
            "설계 DB 는 인증 DB 와 별도의 데이터베이스다. "
            "(SQLite 로 돌릴 것이면 DATABASE_BACKEND=sqlite)")
    base = Path(os.environ.get("CAPSTONE_DATA_DIR") or ROOT / "data")
    return f"sqlite:///{base / 'portfolio_design.db'}"


def get_test_database_url() -> str | None:
    return os.environ.get("TEST_DATABASE_URL", "").strip() or None
