"""테스트가 원격 DB 로 새지 않는지 확인한다.

운영이 PostgreSQL 로 넘어가면 .env.local 에 운영 접속 정보가 들어간다.
src/db/config.py 가 import 시점에 그 파일을 읽으므로 pytest 환경에도 들어온다.
그 상태에서 forward 의 connect() 는 backend 가 postgres 면 파일 경로를 무시하고
DATABASE_URL 로 가버린다. tests/conftest.py 의 세션 픽스처가 그걸 막는다.

이 파일은 그 안전장치 자체를 검사한다. 여기가 깨지면 다른 테스트들이
조용히 운영 DB 를 건드리기 시작한다.
"""
import os


def test_백엔드가_sqlite로_고정된다():
    from src.db.config import get_backend
    assert get_backend() == "sqlite"


def test_원격_주소가_환경에서_제거된다():
    assert not os.environ.get("DATABASE_URL")
    assert not os.environ.get("CAPSTONE_DESIGN_DATABASE_URL")


def test_connect가_넘겨받은_파일을_연다(tmp_path):
    """backend 가 sqlite 면 경로를 그대로 쓴다. postgres 면 무시하고 URL 로 간다."""
    from src.forward.db import connect
    db = tmp_path / "probe.db"
    con = connect(db)
    try:
        con.execute("CREATE TABLE t (x INTEGER)")
        con.execute("INSERT INTO t VALUES (1)")
        con.commit()
        assert con.execute("SELECT COUNT(*) AS n FROM t").fetchone()["n"] == 1
    finally:
        con.close()
    assert db.is_file(), "연결이 지정한 파일로 가지 않았다"


def test_설계_DB도_파일을_가리킨다():
    """CAPSTONE_DESIGN_DATABASE_URL 이 지워졌으니 파일 규칙으로 떨어져야 한다."""
    from src.db.config import get_design_database_url
    saved = {k: os.environ.get(k) for k in ("CAPSTONE_DEMO", "APP_PROFILE")}
    os.environ["CAPSTONE_DEMO"] = "1"
    os.environ["APP_PROFILE"] = "local"
    try:
        url = get_design_database_url()
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
    assert url.startswith("sqlite:///"), url
