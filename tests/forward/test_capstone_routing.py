"""캡스톤 모드 DB 라우팅: forward 엔진과 대시보드가 같은 DB 를 본다.

합의(2번안): CAPSTONE_DEMO 모드를 유지하면서 forward 운용 기록을 설계 DB
(portfolio_design.db)에 남긴다. 비교 시연 데이터가 있는 capstone_demo.db 는
건드리지 않아 서로 덮어쓰지 않는다.
"""
from __future__ import annotations

import os
import re
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def envs(**kv):
    """테스트 사이에 환경변수가 새지 않도록 복원한다."""
    old = {k: os.environ.get(k) for k in kv}
    try:
        for k, v in kv.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


CAPSTONE = dict(CAPSTONE_DEMO="1", APP_PROFILE="local", DATABASE_BACKEND="sqlite")


def test_캡스톤_모드에서_forward는_설계_DB를_본다(tmp_path):
    from src.forward.runtime import get_database_path
    with envs(**CAPSTONE, CAPSTONE_DATA_DIR=str(tmp_path)):
        assert get_database_path() == tmp_path / "portfolio_design.db"


def test_대시보드가_읽는_경로와_같다(tmp_path):
    """API 는 인증 DB 와 같은 디렉터리의 portfolio_design.db 를 쓴다."""
    from src.db.config import get_database_url
    from src.forward.runtime import get_database_path
    with envs(**CAPSTONE, CAPSTONE_DATA_DIR=str(tmp_path)):
        auth = Path(get_database_url().replace("sqlite:///", ""))
        assert auth.name == "capstone_demo.db"          # 시연 데이터는 여기
        assert auth.with_name("portfolio_design.db") == get_database_path()


def test_시연_DB와_운용_DB는_다른_파일이다(tmp_path):
    from src.db.config import get_database_url
    from src.forward.runtime import get_database_path
    with envs(**CAPSTONE, CAPSTONE_DATA_DIR=str(tmp_path)):
        assert Path(get_database_url().replace("sqlite:///", "")) != get_database_path()


def test_캡스톤_모드가_아니면_기존_경로를_유지한다(tmp_path):
    from src.forward.runtime import ROOT, get_database_path
    with envs(CAPSTONE_DEMO=None, APP_PROFILE="local", CAPSTONE_DATA_DIR=str(tmp_path)):
        assert get_database_path() == ROOT / "data" / "forward_local.db"
    with envs(CAPSTONE_DEMO="1", APP_PROFILE="live", CAPSTONE_DATA_DIR=str(tmp_path)):
        assert get_database_path() == ROOT / "data" / "forward_test.db"
    with envs(CAPSTONE_DEMO="1", APP_PROFILE="demo", CAPSTONE_DATA_DIR=str(tmp_path)):
        assert get_database_path() == ROOT / "data" / "forward_demo.db"


def test_배너에_설계_DB와_모드가_표시된다(tmp_path):
    from src.forward.runtime import safety_banner
    with envs(**CAPSTONE, CAPSTONE_DATA_DIR=str(tmp_path)):
        banner = safety_banner()
        assert "PROFILE: LOCAL" in banner
        assert "MODE: CAPSTONE" in banner
        assert "portfolio_design.db" in banner


def test_캡스톤_모드가_아니면_배너가_STANDARD다(tmp_path):
    """배너만 보고 어느 DB 를 쓰는지 판단할 수 있어야 한다."""
    from src.forward.runtime import safety_banner
    with envs(CAPSTONE_DEMO=None, APP_PROFILE="local", CAPSTONE_DATA_DIR=str(tmp_path)):
        banner = safety_banner()
        assert "MODE: STANDARD" in banner
        assert "forward_local.db" in banner


def test_runtime_import이_dotenv를_로드한다():
    """CAPSTONE_DEMO 를 .env.local 에만 둔 경우에도 라우팅이 흔들리지 않아야 한다.

    runtime 이 os.environ 을 직접 읽으므로, dotenv 로드가 호출 경로에 따라
    늦어지면 같은 명령이 다른 DB 를 가리킨다. import 시점에 로드되는지 본다.
    """
    import src.forward.runtime as rt
    assert getattr(rt, "_dbconfig", None) is not None, \
        "runtime 이 src.db.config 를 import 하지 않는다(dotenv 로드 누락)"


# --------------------------------------------------------------------------
# 백엔드 설정 충돌 방지
# --------------------------------------------------------------------------

LIVE_URL_ONLY = dict(APP_PROFILE="live", DATABASE_BACKEND="sqlite",
                     DATABASE_URL="postgresql+psycopg://u:p@h/db",
                     CAPSTONE_DEMO=None)


def test_CI에서_URL만_주면_거부한다():
    """DATABASE_BACKEND 를 빼먹으면 sqlite 기본값으로 빈 파일에 기록된다.

    CI 는 체크아웃이 매번 새로 생기므로 배치가 '성공'하면서 데이터가 남지 않는다.
    """
    from src.forward.runtime import assert_backend_consistent
    with envs(**LIVE_URL_ONLY, CI="true", GITHUB_ACTIONS=None):
        try:
            assert_backend_consistent()
        except RuntimeError as exc:
            assert "DATABASE_BACKEND" in str(exc)
        else:
            raise AssertionError("설정 충돌을 잡지 못했다")


def test_로컬에서는_경고만_내고_막지_않는다():
    """기존 SQLite 파일에 live 로 돌리는 것은 정당하다(테스트가 그렇게 한다)."""
    from src.forward.runtime import assert_backend_consistent
    with envs(**LIVE_URL_ONLY, CI=None, GITHUB_ACTIONS=None):
        assert_backend_consistent()   # 예외가 나면 실패


def test_live에서_backend까지_맞으면_통과한다():
    from src.forward.runtime import assert_backend_consistent
    with envs(APP_PROFILE="live", DATABASE_BACKEND="postgres",
              DATABASE_URL="postgresql+psycopg://u:p@h/db", CAPSTONE_DEMO=None,
              CI="true"):
        assert_backend_consistent()


def test_live가_아니면_남아있는_URL을_문제삼지_않는다():
    """캡스톤은 sqlite 로 돌고, .env.local 에 Neon URL 이 남아 있을 수 있다."""
    from src.forward.runtime import assert_backend_consistent
    for profile in ("local", "demo", "validation"):
        with envs(APP_PROFILE=profile, DATABASE_BACKEND="sqlite",
                  DATABASE_URL="postgresql+psycopg://u:p@h/db", CI="true"):
            assert_backend_consistent()


def test_URL이_없으면_sqlite도_정상이다():
    from src.forward.runtime import assert_backend_consistent
    with envs(APP_PROFILE="live", DATABASE_BACKEND="sqlite", DATABASE_URL=None,
              CAPSTONE_DEMO=None, CI="true"):
        assert_backend_consistent()


def test_워크플로가_DATABASE_BACKEND를_넘긴다():
    """CI 크론이 DATABASE_URL 만 주고 backend 를 빼먹으면 조용히 실패한다."""
    root = Path(__file__).resolve().parents[2]
    wf = root / ".github" / "workflows"
    if not wf.is_dir():
        return
    for name in ("daily_forward.yml", "monthly_rebalance.yml", "weekly_views.yml"):
        f = wf / name
        if not f.is_file():
            continue
        text = f.read_text(encoding="utf-8")
        if "DATABASE_URL" in text and "APP_PROFILE: live" in text:
            assert "DATABASE_BACKEND: postgres" in text, \
                f"{name}: DATABASE_URL 만 있고 DATABASE_BACKEND 가 없다"


def test_배너에_백엔드가_표시된다(tmp_path):
    from src.forward.runtime import safety_banner
    with envs(**CAPSTONE, CAPSTONE_DATA_DIR=str(tmp_path)):
        assert "BACKEND: SQLITE" in safety_banner()


def test_forward_테이블_이름이_ORM과_전부_일치한다():
    """두 엔진이 같은 파일을 쓰므로 테이블 이름이 어긋나면 데이터가 갈라진다."""
    root = Path(__file__).resolve().parents[2]
    orm = set()
    for f in (root / "src" / "db" / "models").glob("*.py"):
        orm |= set(re.findall(r'__tablename__\s*=\s*["\']([a-z_]+)["\']',
                              f.read_text(encoding="utf-8")))
    fwd = set(re.findall(r"CREATE TABLE IF NOT EXISTS ([a-z_]+)",
                         (root / "src" / "forward" / "db.py").read_text(encoding="utf-8")))
    assert fwd, "forward SCHEMA 를 읽지 못했다"
    assert fwd - orm == set(), f"ORM 에 없는 forward 테이블: {sorted(fwd - orm)}"
