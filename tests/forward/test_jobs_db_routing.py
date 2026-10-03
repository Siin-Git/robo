"""작업 기록(scheduled_jobs)이 **어느 데이터베이스로 가는지** 고정한다.

2026-10-01 에 이것 때문에 사고가 났다. 캡스톤 모드는 DB 가 둘이다.

    인증·비교 시연 : DATABASE_URL                      (robo_auth)
    설계·운용 기록 : CAPSTONE_DESIGN_DATABASE_URL      (robo_design)  <- 원장

그런데 `_engine_for` 는 postgres 면 무조건 `create_app_engine()`, 즉 인증 DB 로
갔다. SQLite 로 돌 때는 파일이 하나뿐이라 아무 일도 없었지만, PostgreSQL 로
옮기는 순간 scheduled_jobs 를 **빈 인증 DB** 에서 찾게 된다. 기록이 없으니 매번
"아직 안 돌았다"로 판정하고, 중복 실행 방지가 통째로 사라진다.

그날 월간 리밸런싱이 두 번 돌아 벤치마크 계좌 3개에 중복 주문 26건이 생겼다
(전부 buy 였다. 체결됐으면 목표 비중을 두 번 사서 현금이 음수가 됐을 것이다).

여기서는 **엔진을 실제로 만들지 않고** 어떤 URL 이 선택되는지만 본다. 틀린
라우팅은 접속이 성공해도 조용히 잘못된 곳에 쓰기 때문에, 잡아야 하는 것은
연결 성공 여부가 아니라 "어느 주소를 골랐는가" 다.
"""
import pytest

from src.forward import jobs as J

AUTH = "postgresql+psycopg://u:p@host/robo_auth"
DESIGN = "postgresql+psycopg://u:p@host/robo_design"


@pytest.fixture
def chosen(monkeypatch):
    """create_app_engine 에 넘어간 URL 들을 모은다 (None = 스스로 환경에서 읽음)."""
    seen = []

    def fake_create_app_engine(url=None, backend=None):
        seen.append(url)
        return object()

    monkeypatch.setattr("src.db.session.create_app_engine", fake_create_app_engine)
    return seen


def _capstone(monkeypatch, backend="postgres"):
    monkeypatch.setenv("APP_PROFILE", "local")
    monkeypatch.setenv("CAPSTONE_DEMO", "1")
    monkeypatch.setenv("DATABASE_BACKEND", backend)


def test_캡스톤_postgres_는_설계_DB_로_간다(chosen, monkeypatch):
    _capstone(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", AUTH)
    monkeypatch.setenv("CAPSTONE_DESIGN_DATABASE_URL", DESIGN)

    J._engine_for(None, sqlite_path="/없는경로.db")

    assert chosen == [DESIGN], (
        "작업 기록은 원장과 같은 DB(설계 DB)에 있어야 한다. 인증 DB 로 가면 "
        "scheduled_jobs 가 비어 있어 중복 실행 방지가 무력해진다.")


def test_캡스톤이_아니면_예전대로_DATABASE_URL_로_간다(chosen, monkeypatch):
    monkeypatch.delenv("CAPSTONE_DEMO", raising=False)
    monkeypatch.setenv("APP_PROFILE", "live")
    monkeypatch.setenv("DATABASE_BACKEND", "postgres")
    monkeypatch.setenv("DATABASE_URL", AUTH)

    J._engine_for(None, sqlite_path="/없는경로.db")

    # create_app_engine() 가 인자 없이 불려 스스로 DATABASE_URL 을 읽는다.
    assert chosen == [None]


def test_sqlite_는_넘겨받은_파일을_그대로_쓴다(chosen, monkeypatch, tmp_path):
    _capstone(monkeypatch, backend="sqlite")
    p = tmp_path / "fwd.db"

    J._engine_for(None, sqlite_path=p)

    assert chosen == [f"sqlite:///{p}"], "로컬 SQLite 동작은 바뀌면 안 된다"


def test_명시한_URL_이_항상_이긴다(chosen, monkeypatch):
    _capstone(monkeypatch)
    monkeypatch.setenv("CAPSTONE_DESIGN_DATABASE_URL", DESIGN)

    J._engine_for("sqlite:///explicit.db", sqlite_path="/없는경로.db")

    assert chosen == ["sqlite:///explicit.db"]


def test_캡스톤_postgres_인데_설계_URL_이_없으면_소리내어_죽는다(chosen, monkeypatch):
    """조용히 인증 DB 로 넘어가면 안 된다. 그게 이번 사고의 형태였다."""
    _capstone(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", AUTH)
    monkeypatch.delenv("CAPSTONE_DESIGN_DATABASE_URL", raising=False)

    with pytest.raises(ValueError):
        J._engine_for(None, sqlite_path="/없는경로.db")

    assert chosen == [], "엔진을 만들기 전에 멈출야 한다"
