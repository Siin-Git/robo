"""Runtime profile resolver: single source of truth for environment separation.

Profiles: live / demo / validation. Every forward CLI resolves its database
through here and prints the safety banner. No module may hardcode a DB path.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# .env / .env.local 을 여기서 반드시 로드한다.
# 이 모듈이 CAPSTONE_DEMO 등을 os.environ 에서 직접 읽으므로, dotenv 로드가
# 호출 경로에 따라 늦어지면 같은 명령이 다른 DB 를 가리키게 된다(조용한 사고).
# src/db/config.py 가 import 시점에 로드하므로 그것을 단일 창구로 쓴다.
# 프로세스 환경변수가 항상 파일보다 우선한다.
try:
    from ..db import config as _dbconfig  # noqa: F401
except Exception:  # dotenv 미설치 등 - 프로세스 환경변수만으로 동작한다
    pass

PROFILES = ("live", "demo", "validation", "local")
DB_PATHS = {
    "live": "data/forward_test.db",
    "demo": "data/forward_demo.db",
    "validation": "data/forward_validation.db",
    "local": "data/forward_local.db",
}


def get_runtime_profile() -> str:
    profile = os.environ.get("APP_PROFILE", "live").strip().lower()
    if profile not in PROFILES:
        raise ValueError(f"unknown APP_PROFILE={profile!r} (expected one of {PROFILES})")
    return profile


def capstone_design_db() -> Path | None:
    """캡스톤 모드에서 API 가 읽는 설계 워크스페이스 DB 경로.

    이 모드가 아니면 None. 경로 규칙은 ``src/api/design_workspace.py`` 와
    같아야 한다(인증 DB 와 같은 디렉터리의 portfolio_design.db).
    """
    if os.environ.get("CAPSTONE_DEMO") != "1":
        return None
    if os.environ.get("APP_PROFILE", "live").strip().lower() != "local":
        return None
    base = Path(os.environ.get("CAPSTONE_DATA_DIR") or (ROOT / "data"))
    return base / "portfolio_design.db"


def get_database_path(profile: str | None = None) -> Path:
    profile = profile or get_runtime_profile()
    if profile not in PROFILES:
        raise ValueError(f"unknown profile {profile!r}")
    # 캡스톤 모드에서는 운용 기록을 대시보드가 읽는 DB 에 남긴다.
    # (13명 비교 시연 데이터는 capstone_demo.db 에 그대로 두어 섞이지 않는다)
    design = capstone_design_db()
    if design is not None and profile == "local":
        return design
    return ROOT / DB_PATHS[profile]


def get_backend_name() -> str:
    """현재 DB 백엔드. src.db.config 를 거쳐 .env 값도 반영한다."""
    try:
        from ..db.config import get_backend
        return get_backend()
    except Exception:
        return os.environ.get("DATABASE_BACKEND", "sqlite").strip().lower()


def in_ci() -> bool:
    """GitHub Actions 등 CI 러너에서 실행 중인지."""
    return any(os.environ.get(k, "").strip().lower() in ("1", "true", "yes")
               for k in ("CI", "GITHUB_ACTIONS"))


def assert_backend_consistent(profile: str | None = None) -> None:
    """LIVE 에서 DATABASE_URL 만 주고 backend 를 빼먹은 설정을 잡는다.

    get_backend() 의 기본값은 sqlite 다. 그래서 DATABASE_URL 을 넣고
    DATABASE_BACKEND 를 빼면 PostgreSQL 이 아니라 로컬 SQLite 파일에 기록한다.

    CI 러너에서는 거부한다: 체크아웃이 매번 새로 생기므로 빈 파일에 쓰고
    끝나고, 배치가 '성공'하면서 데이터가 남지 않는다(조용한 실패).

    로컬에서는 경고만 낸다: 기존 SQLite 파일을 상대로 live 프로파일을
    돌리는 것은 정당하고(테스트가 그렇게 한다), .env.local 에 지금 쓰지 않는
    DATABASE_URL 이 남아 있는 것도 흔하다.

    LOCAL/DEMO/VALIDATION 프로파일은 아예 검사하지 않는다.
    """
    profile = profile or get_runtime_profile()
    if profile != "live":
        return
    url = os.environ.get("DATABASE_URL", "").strip()
    backend = get_backend_name()
    if not url or backend == "postgres":
        return
    msg = ("설정 충돌: DATABASE_URL 이 있는데 DATABASE_BACKEND 가 "
           f"{backend!r} 다. 이 상태로는 PostgreSQL 이 아니라 로컬 SQLite "
           "파일에 기록한다. DATABASE_BACKEND=postgres 를 설정하거나, "
           "SQLite 로 돌릴 것이면 DATABASE_URL 을 비울 것.")
    if in_ci():
        raise RuntimeError(
            msg + "\n(CI 에서는 체크아웃이 매번 새로 생겨 빈 파일에 쓰고 "
            "끝나므로 거부한다.)")
    print(f"WARNING: {msg}", file=sys.stderr, flush=True)


def safety_banner(profile: str | None = None) -> str:
    profile = profile or get_runtime_profile()
    db = get_database_path(profile)
    try:
        disp = str(db.relative_to(ROOT))
    except ValueError:
        disp = str(db)
    mode = "CAPSTONE (design workspace)" if capstone_design_db() is not None else "STANDARD"
    backend = get_backend_name()
    if backend == "postgres":
        disp = "PostgreSQL (DATABASE_URL)"
    return ("=====================================\n"
            f"PROFILE: {profile.upper()}\n"
            f"MODE: {mode}\n"
            f"BACKEND: {backend.upper()}\n"
            f"DATABASE: {disp}\n"
            "=====================================")


def print_banner(profile: str | None = None) -> str:
    profile = profile or get_runtime_profile()
    print(safety_banner(profile), flush=True)
    assert_backend_consistent(profile)
    return profile
