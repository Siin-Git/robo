"""NAV 이력의 단위를 못 박는다.

``nav_daily`` 에는 값이 둘 있다.

- ``nav``          : 원화 평가액. 초기자본 1억이라 1e8 규모다.
- ``nav_base100``  : 운용 시작을 100 으로 놓은 지수.

화면은 받은 값을 100 기준으로 읽어 수익률을 만든다(``(v / 100 - 1) * 100``).
그래서 ``nav_history`` 는 반드시 **기준 100** 값을 돌려줘야 한다.

예전에는 ``nav`` 을 돌려줬다. 시연 DB 는 가상 NAV 를 두 컬럼에 같은 값으로
넣기 때문에 우연히 맞았고, 운용 기록을 같은 DB 에서 읽게 된 뒤에야
화면에 ``99,642,385.5%`` 가 찍히면서 드러났다. 두 값이 **크게 다른** 행을
넣어 두면 그 실수가 다시 들어올 때 여기서 걸린다.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from src.api.services.performance_service import nav_history
from src.db.base import Base
from src.db.models.account import Account
from src.db.models.nav import NavDaily
from src.db.models.participant import Participant
from src.db.session import create_app_engine, session_factory

# 2026-09-29 설계 DB 의 실제 값. 사고가 난 바로 그 행이다.
KRW = [Decimal("100000000.00"), Decimal("99642485.45")]
BASE100 = [Decimal("100.00000000"), Decimal("99.69230000")]
DATES = [date(2026, 9, 28), date(2026, 9, 29)]


def _add_account(session, account_id, account_type):
    now = datetime.now(timezone.utc)
    session.add(Account(account_id=account_id, participant_id="P001",
                        account_type=account_type, shadow_name=None,
                        benchmark_version="CORE_V0.3", inception_date=DATES[0],
                        initial_capital_krw=Decimal("100000000"), status="active",
                        created_at=now))
    for d, krw, b100 in zip(DATES, KRW, BASE100):
        session.add(NavDaily(account_id=account_id, date=d, nav=krw, nav_base100=b100,
                             daily_return=None, cumulative_return=Decimal("0"),
                             cash_balance=Decimal("0"), stale_price_flag=False,
                             nav_status="OK", benchmark_version="CORE_V0.3",
                             theme_universe_version="T", risk_model_version="R",
                             execution_rule_version="E"))


@pytest.fixture()
def session(tmp_path):
    engine = create_app_engine(f"sqlite:///{tmp_path}/nav.db")
    Base.metadata.create_all(engine)
    with session_factory(engine)() as s:
        now = datetime.now(timezone.utc)
        s.add(Participant(participant_id="P001", display_name="단위 검증", status="active",
                          join_date=DATES[0], leave_date=None,
                          created_at=now, updated_at=now))
        _add_account(s, "A-P001-PERSONAL", "personal")
        _add_account(s, "A-P001-CORE", "core")
        s.commit()
        yield s


def test_기준100_값을_돌려준다(session):
    items = nav_history(session, "P001")["items"]
    assert len(items) == 2
    assert items[-1]["personalized_nav"] == pytest.approx(99.6923, abs=1e-6)
    assert items[-1]["core_nav"] == pytest.approx(99.6923, abs=1e-6)


def test_원화_금액이_새어나오지_않는다(session):
    """1e8 규모 값이 나오면 ``nav`` 을 돌려주고 있다는 뜻이다."""
    for item in nav_history(session, "P001")["items"]:
        for key in ("personalized_nav", "core_nav"):
            value = item[key]
            assert value is not None
            assert 1.0 < value < 10_000.0, (
                f"{key}={value!r} 는 지수 범위를 벗어난다. 원화 평가액을 "
                f"돌려주고 있지 않은지 확인할 것")


def test_화면_공식을_적용하면_말이_되는_수익률이_나온다(session):
    """프론트는 ``(v / 100 - 1) * 100`` 으로 퍼센트를 만든다.

    사고 당시 이 값이 99,642,385.5 였다. 이틀치 수익률이므로 한 자릿수
    퍼센트 안에 들어와야 한다.
    """
    items = nav_history(session, "P001")["items"]
    percent = (items[-1]["personalized_nav"] / 100 - 1) * 100
    assert percent == pytest.approx(-0.3077, abs=1e-3)
    assert abs(percent) < 10.0


def test_시작일은_100_이다(session):
    first = nav_history(session, "P001")["items"][0]
    assert first["personalized_nav"] == pytest.approx(100.0, abs=1e-6)
    assert first["core_nav"] == pytest.approx(100.0, abs=1e-6)
