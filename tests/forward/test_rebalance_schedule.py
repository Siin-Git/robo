"""리밸런싱 주기와 효력일 규칙.

두 가지를 고정한다.

1. 효력일은 결정 기준일(asof)의 다음 거래일이다. 제출 시점보다 미래여야 한다.
   예전 run_monthly 는 그 달 1일로 잡아서, 9월 30일 데이터로 판단한 주문이
   9월 1일 효력으로 만들어졌다. 나중 데이터로 판단해 이전 종가에 체결하는
   형태라 실제로 불가능한 거래다(inception 가드가 막아 주문만 쌓였다).

2. frequency=quarterly 면 3·6·9·12월 말에만 리밸런싱한다.
"""
from datetime import date

import pytest

from src.forward.rebalance_schedule import (
    QUARTER_END_MONTHS, effective_date, is_rebalance_period,
    next_rebalance_effective, next_trading_weekday, normalize_frequency,
    period_asof, skip_reason)


# --------------------------------------------------------------------------
# frequency
# --------------------------------------------------------------------------

@pytest.mark.parametrize("value, expected", [
    ("monthly", "monthly"), ("quarterly", "quarterly"),
    ("MONTHLY", "monthly"), (" Quarterly ", "quarterly"), (None, "monthly"),
])
def test_주기값_정규화(value, expected):
    assert normalize_frequency(value) == expected


def test_모르는_주기는_거부한다():
    """조용히 monthly 로 떨어지면 설정 오타를 알아챌 수 없다."""
    for bad in ("weekly", "yearly", "분기"):
        try:
            normalize_frequency(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{bad!r} 를 통과시켰다")


@pytest.mark.parametrize("month", range(1, 13))
def test_monthly는_모든_달에_실행한다(month):
    assert is_rebalance_period(2026, month, "monthly") is True


@pytest.mark.parametrize("month", range(1, 13))
def test_quarterly는_분기말에만_실행한다(month):
    expected = month in QUARTER_END_MONTHS
    assert is_rebalance_period(2026, month, "quarterly") is expected


def test_분기말은_3_6_9_12월이다():
    assert QUARTER_END_MONTHS == (3, 6, 9, 12)


# --------------------------------------------------------------------------
# 효력일
# --------------------------------------------------------------------------

def test_기준일_다음_거래일이_효력일이다():
    # 2026-09-30 은 수요일 -> 10-01 목요일
    assert effective_date("2026-09-30") == "2026-10-01"


def test_효력일은_항상_기준일보다_뒤다():
    """예전 버그: --month 2026-09 가 effective 2026-09-01 을 만들었다."""
    for y, m in [(2026, 9), (2026, 10), (2026, 12), (2027, 1)]:
        asof = period_asof(y, m)
        assert effective_date(asof) > asof, f"{y}-{m}: 효력일이 과거다"


def test_주말은_건너뛴다():
    # 2026-10-31 은 토요일 -> 11-02 월요일
    assert effective_date("2026-10-31") == "2026-11-02"
    # 2027-01-01 은 금요일 -> 01-04 월요일
    assert next_trading_weekday(date(2027, 1, 1)) == date(2027, 1, 4)


def test_views의_next_weekday와_같은_결과다():
    """두 구현이 갈라지면 엔진과 API 가 다른 날짜를 쓰게 된다."""
    from src.forward.views import next_weekday
    d = date(2026, 1, 1)
    for _ in range(400):
        assert effective_date(d.isoformat()) == next_weekday(d.isoformat()), d
        d = date.fromordinal(d.toordinal() + 1)


def test_월_마지막날_계산():
    assert period_asof(2026, 9) == "2026-09-30"
    assert period_asof(2026, 2) == "2026-02-28"
    assert period_asof(2028, 2) == "2028-02-29"   # 윤년


# --------------------------------------------------------------------------
# 다음 리밸런싱 (API 의 next_rebalance_date)
# --------------------------------------------------------------------------

def test_monthly_다음_리밸런싱():
    # 2026-09-11 기준 -> 09-30 말일 -> 10-01
    assert next_rebalance_effective(date(2026, 9, 11), "monthly") == date(2026, 10, 1)


def test_quarterly_다음_리밸런싱():
    # 9월은 분기말이므로 monthly 와 같다
    assert next_rebalance_effective(date(2026, 9, 11), "quarterly") == date(2026, 10, 1)
    # 10월 중순이면 다음은 12월 말 -> 2027-01-01(금)
    assert next_rebalance_effective(date(2026, 10, 15), "quarterly") == date(2027, 1, 1)
    # monthly 라면 10-31(토) 다음 평일
    assert next_rebalance_effective(date(2026, 10, 15), "monthly") == date(2026, 11, 2)


def test_분기_경계를_넘어간다():
    assert next_rebalance_effective(date(2026, 4, 1), "quarterly") == date(2026, 7, 1)
    assert next_rebalance_effective(date(2026, 11, 20), "quarterly") == date(2027, 1, 1)


def test_다음_리밸런싱은_항상_기준일보다_뒤다():
    d = date(2026, 1, 1)
    for _ in range(400):
        for freq in ("monthly", "quarterly"):
            nxt = next_rebalance_effective(d, freq)
            assert nxt is not None and nxt > d, f"{d} {freq} -> {nxt}"
        d = date.fromordinal(d.toordinal() + 1)


# --------------------------------------------------------------------------
# 설정 연결
# --------------------------------------------------------------------------

def test_config의_주기가_유효한_값이다():
    from src.forward.config import load_forward_config
    freq = load_forward_config()["forward_test"]["core_rebalance"]["frequency"]
    assert normalize_frequency(freq) in ("monthly", "quarterly")


def test_건너뛰는_이유가_설명을_담는다():
    msg = skip_reason(2026, 10, "quarterly")
    assert "2026-10" in msg and "quarterly" in msg


def test_previous_month_effective_date_can_still_be_upcoming():
    assert next_rebalance_effective(date(2026, 11, 1), "monthly") == date(2026, 11, 2)
    assert next_rebalance_effective(date(2023, 4, 1), "quarterly") == date(2023, 4, 3)
