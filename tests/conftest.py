import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# 테스트에서 원격 DB 로 새어나가지 못하게 막는 변수들.
REMOTE_ENV = ("DATABASE_BACKEND", "DATABASE_URL", "CAPSTONE_DESIGN_DATABASE_URL")


@pytest.fixture(scope="session", autouse=True)
def _never_touch_remote_db():
    """테스트는 절대 원격 데이터베이스에 붙지 않는다.

    운영을 PostgreSQL 로 옮기면 개발자의 ``.env.local`` 에
    ``DATABASE_BACKEND=postgres`` 와 운영 ``DATABASE_URL`` 이 들어간다.
    ``src/db/config.py`` 가 import 시점에 그 파일을 읽으므로, 아무것도 하지
    않으면 pytest 프로세스의 환경에도 그대로 들어온다.

    그 상태에서 ``src/forward/db.py`` 의 ``connect()`` 는 backend 가 postgres 면
    **넘겨받은 파일 경로를 무시하고** ``DATABASE_URL`` 로 간다. forward 테스트
    열두 파일이 ``connect()`` 를 부르므로, 결과적으로 **pytest 가 운영 DB 에
    테이블을 만들고 데이터를 쓴다.** 실제로 비슷한 사고가 한 번 있었다
    (설계 DB URL 을 환경변수에서 먼저 읽던 시절).

    그래서 세션 전체에서 SQLite 로 못 박고 원격 주소를 지운다. 특정 테스트가
    postgres 동작을 보려면 스스로 환경을 세웠다 되돌리면 된다(그 쪽이 이긴다).
    PostgreSQL 통합 테스트는 ``TEST_DATABASE_URL`` 이라는 별도 변수를 쓰므로
    여기서 건드리지 않는다.
    """
    saved = {k: os.environ.get(k) for k in REMOTE_ENV}
    os.environ["DATABASE_BACKEND"] = "sqlite"
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("CAPSTONE_DESIGN_DATABASE_URL", None)
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
